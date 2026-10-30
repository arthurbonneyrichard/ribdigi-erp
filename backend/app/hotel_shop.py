"""Hotel shop till: walk-up sales and room charges on hotel's own tables.

Sales land on ``hotel_shop_sales`` (never retail ``transactions``). Cash, card,
Mobile Money and wallet sales go through the open front-desk cashier shift and
post a sale journal. "Charge to room" adds one charge to the guest's open folio
(paid at checkout, where the folio invoice carries the revenue) and posts only
the cost of goods now. Stock comes off at the sale and goes back on a refund.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import hotel as hotel_svc
from app import hotel_pms
from app import inventory
from app import models as m
from app import tax as tax_svc
from app.honesty import money_json, optional_honest_narrative

TILL_METHODS = frozenset({"cash", "card", "mobile_money", "wallet"})
ROOM = "room"
REF = "hotel_shop_sale"


def _now() -> datetime:
    return datetime.utcnow()


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


async def list_shop_items(db: AsyncSession, tenant_id: str) -> list[dict]:
    """Things the shop sells: active products with a selling price."""
    rows = (
        await db.execute(
            select(m.Product)
            .where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True), m.Product.selling_price > 0)
            .order_by(m.Product.name.asc())
        )
    ).scalars()
    return [
        {
            "id": row.id,
            "name": row.name,
            "price": _money(row.selling_price),
            "category": (row.category or "Shop").strip() or "Shop",
            "stock_qty": money_json(row.stock_qty or 0),
            "has_image": bool(getattr(row, "image_url", None)),
        }
        for row in rows
    ]


async def open_room_folios(db: AsyncSession, tenant_id: str) -> list[dict]:
    """In-house guests whose folio is open, so the shop can charge to their room."""
    rows = (
        await db.execute(
            select(m.HotelFolio, m.HotelGuest, m.HotelReservation, m.HotelRoom)
            .join(m.HotelGuest, m.HotelGuest.id == m.HotelFolio.guest_id)
            .join(m.HotelReservation, m.HotelReservation.id == m.HotelFolio.reservation_id)
            .outerjoin(m.HotelRoom, m.HotelRoom.id == m.HotelReservation.room_id)
            .where(m.HotelFolio.tenant_id == tenant_id, m.HotelFolio.status == "open")
            .order_by(m.HotelFolio.opened_at.desc())
        )
    ).all()
    out = []
    for folio, guest, reservation, room in rows:
        out.append({
            "folio_id": folio.id,
            "folio_number": folio.folio_number,
            "guest_name": guest.full_name or "Guest",
            "room": room.code if room else None,
            "reservation_status": reservation.status,
        })
    return out


async def _next_number(db: AsyncSession, tenant_id: str) -> str:
    count = (
        await db.execute(select(func.count()).select_from(m.HotelShopSale).where(m.HotelShopSale.tenant_id == tenant_id))
    ).scalar_one()
    return f"HS-{int(count or 0) + 1:04d}"


async def _sale_lines(db: AsyncSession, sale: m.HotelShopSale) -> list[m.HotelShopSaleLine]:
    return list(
        (
            await db.execute(select(m.HotelShopSaleLine).where(m.HotelShopSaleLine.sale_id == sale.id))
        ).scalars()
    )


async def _move_stock(db, tenant_id: str, sale: m.HotelShopSale, *, user_id, sign: float) -> None:
    for line in await _sale_lines(db, sale):
        await inventory.apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=line.product_id,
            quantity_delta=money_json(float(line.quantity) * sign),
            movement_type="stock_out" if sign < 0 else "stock_in",
            user_id=user_id,
            reference_type=REF,
            reference_id=sale.id,
            notes=f"Hotel shop {sale.sale_number}",
        )


async def _post_journal(db, tenant_id: str, sale: m.HotelShopSale, *, user_id, reverse: bool) -> str | None:
    await accounting.ensure_default_accounts(db, tenant_id)
    description = f"Hotel shop {'refund' if reverse else 'sale'} {sale.sale_number}"
    lines: list[dict] = []
    if sale.payment_method != ROOM and _money(sale.total) > 0:
        # Room charges carry their revenue on the folio invoice at checkout; only the cost moves now.
        debit_code, _label = accounting.pos_debit_account_for_payment_method(sale.payment_method)
        revenue = _money(float(sale.total) - float(sale.tax))
        tax = _money(sale.tax)
        if reverse:
            lines = [
                {"account_code": "4000", "debit": revenue, "credit": 0, "description": description},
                {"account_code": debit_code, "debit": 0, "credit": _money(sale.total), "description": description},
            ]
            if tax > 0:
                lines.insert(1, {"account_code": "2100", "debit": tax, "credit": 0, "description": description})
        else:
            lines = [
                {"account_code": debit_code, "debit": _money(sale.total), "credit": 0, "description": description},
                {"account_code": "4000", "debit": 0, "credit": revenue, "description": description},
            ]
            if tax > 0:
                lines.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    stock_lines = [{"product_id": line.product_id, "quantity": line.quantity} for line in await _sale_lines(db, sale)]
    cogs = await accounting.compute_standard_cogs(db, tenant_id=tenant_id, lines=stock_lines)
    accounting.append_cogs_lines(lines, cogs, reverse=reverse)
    if not lines:
        return None
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=sale.sale_number,
        source_type=REF,
        source_id=sale.id,
    )
    return entry.id


async def create_sale(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.HotelShopSale:
    method = (payload.payment_method or "cash").strip().lower()
    if method not in TILL_METHODS | {ROOM}:
        raise HTTPException(status_code=422, detail="Choose cash, card, Mobile Money, wallet, or charge to room")
    if not payload.lines:
        raise HTTPException(status_code=422, detail="Add at least one item")
    shift = await hotel_pms.current_shift(db, tenant_id=tenant_id)
    folio = None
    if method == ROOM:
        if not payload.folio_id:
            raise HTTPException(status_code=422, detail="Choose the guest's room")
        folio = await db.get(m.HotelFolio, payload.folio_id)
        if folio is None or folio.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Guest folio not found")
        if folio.status != "open":
            raise HTTPException(status_code=409, detail="That guest has checked out")
    elif shift is None:
        raise HTTPException(status_code=409, detail="Open the front-desk shift before taking money")

    sale = m.HotelShopSale(
        tenant_id=tenant_id,
        sale_number=await _next_number(db, tenant_id),
        store_id=payload.store_id,
        shift_id=shift.id if shift and method != ROOM else None,
        folio_id=folio.id if folio else None,
        customer_name=optional_honest_narrative(payload.customer_name, label="customer name", max_length=180),
        payment_method=method,
        status="completed",
        created_by=user_id,
        created_at=_now(),
    )
    db.add(sale)
    await db.flush()
    subtotal = tax_total = gross_total = 0.0
    words = []
    for line in payload.lines:
        product = await db.get(m.Product, line.product_id)
        if product is None or product.tenant_id != tenant_id or not product.is_active:
            raise HTTPException(status_code=404, detail="Item not found")
        qty = money_json(line.quantity)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Quantity must be above zero")
        price = _money(product.selling_price)
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        net, tax, gross = tax_svc.compute_line_total(qty, price, spec.rate_pct, spec.pricing_mode)
        db.add(
            m.HotelShopSaleLine(
                tenant_id=tenant_id,
                sale_id=sale.id,
                product_id=product.id,
                name=product.name,
                quantity=qty,
                unit_price=price,
                tax=_money(tax),
                line_total=_money(gross),
            )
        )
        subtotal += float(net)
        tax_total += float(tax)
        gross_total += float(gross)
        words.append(f"{int(qty) if qty == int(qty) else qty}x {product.name}")
    sale.subtotal = _money(subtotal)
    sale.tax = _money(tax_total)
    sale.total = _money(gross_total)
    await db.flush()
    await _move_stock(db, tenant_id, sale, user_id=user_id, sign=-1)
    if folio is not None:
        charge = await hotel_svc.add_folio_charge(
            db,
            tenant_id=tenant_id,
            folio_id=folio.id,
            charge_type="extra",
            description=f"Shop {sale.sale_number}: {', '.join(words)}"[:255],
            quantity=1,
            unit_amount=sale.subtotal,
            tax_amount=sale.tax,
            created_by=user_id,
        )
        sale.folio_charge_id = charge.id
    sale.journal_entry_id = await _post_journal(db, tenant_id, sale, user_id=user_id, reverse=False)
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="hotel",
        action="hotel_shop_sale", entity="hotel_shop_sale", entity_id=sale.id,
        details={"sale_number": sale.sale_number, "total": sale.total, "payment_method": method},
    )
    return sale


async def refund_sale(db: AsyncSession, tenant_id: str, sale_id: str, *, user_id: str | None) -> m.HotelShopSale:
    sale = await db.get(m.HotelShopSale, sale_id)
    if sale is None or sale.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.status == "refunded":
        return sale
    if sale.payment_method == ROOM and sale.folio_charge_id:
        folio = await db.get(m.HotelFolio, sale.folio_id) if sale.folio_id else None
        if folio is not None and folio.status != "open":
            raise HTTPException(status_code=409, detail="The guest has checked out; refund it from the guest's bill")
        await hotel_svc.void_folio_charge(
            db, tenant_id=tenant_id, charge_id=sale.folio_charge_id, void_reason=f"Shop refund {sale.sale_number}"
        )
    await _move_stock(db, tenant_id, sale, user_id=user_id, sign=1)
    await _post_journal(db, tenant_id, sale, user_id=user_id, reverse=True)
    sale.status = "refunded"
    sale.refunded_at = _now()
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="hotel",
        action="hotel_shop_refund", entity="hotel_shop_sale", entity_id=sale.id,
        details={"sale_number": sale.sale_number, "total": _money(sale.total)},
    )
    return sale


async def present_sale(db: AsyncSession, sale: m.HotelShopSale) -> dict:
    lines = await _sale_lines(db, sale)
    return {
        "id": sale.id,
        "sale_number": sale.sale_number,
        "status": sale.status,
        "payment_method": sale.payment_method,
        "customer_name": sale.customer_name,
        "folio_id": sale.folio_id,
        "shift_id": sale.shift_id,
        "subtotal": _money(sale.subtotal),
        "tax": _money(sale.tax),
        "total": _money(sale.total),
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
        "items": [
            {"name": line.name, "quantity": money_json(line.quantity), "unit_price": _money(line.unit_price), "line_total": _money(line.line_total)}
            for line in lines
        ],
    }


async def list_sales(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[m.HotelShopSale]:
    return list(
        (
            await db.execute(
                select(m.HotelShopSale)
                .where(m.HotelShopSale.tenant_id == tenant_id)
                .order_by(m.HotelShopSale.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def shift_takings(db: AsyncSession, tenant_id: str) -> dict:
    """Shop takings on the open front-desk shift, by payment method (room charges are separate)."""
    shift = await hotel_pms.current_shift(db, tenant_id=tenant_id)
    if shift is None:
        return {"shift": None, "by_method": {}, "total": 0.0, "sale_count": 0}
    rows = (
        await db.execute(
            select(m.HotelShopSale.payment_method, func.count(), func.coalesce(func.sum(m.HotelShopSale.total), 0))
            .where(
                m.HotelShopSale.tenant_id == tenant_id,
                m.HotelShopSale.shift_id == shift.id,
                m.HotelShopSale.status == "completed",
            )
            .group_by(m.HotelShopSale.payment_method)
        )
    ).all()
    by_method = {method: _money(total) for method, _count, total in rows}
    return {
        "shift": hotel_pms.serialize_shift(shift),
        "by_method": by_method,
        "total": _money(sum(by_method.values())),
        "sale_count": int(sum(int(count or 0) for _m, count, _t in rows)),
    }
