"""Retail till extras: held sales, layaway, and serial-numbered stock.

Held sale: a cart parked while the customer fetches something, picked up again later on any till
of the same store. Nothing moves until it is rung up.

Layaway: goods set aside for a customer who pays in parts. The goods leave sale stock when the
layaway opens (so they cannot be sold twice). Each payment is money held for the customer
(2155 Customer Deposits), not a sale. When the last part is paid the sale is booked: deposits
become revenue and tax, and the cost of the goods moves to cost of sales. A cancelled layaway puts
the goods back; the money is refunded or, with a reason, kept as a cancellation fee.

Serials: a product marked "tracks serial numbers" is received and sold one unit at a time by its
serial, so a phone or a fridge can be traced from delivery to the customer (warranty, theft).
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

DEPOSITS = "2155"
LAYAWAY_METHODS = frozenset({"cash", "card", "mobile_money", "bank_transfer", "wallet"})


# --- held sales ------------------------------------------------------------------------------------


def serialize_held(row: m.PosHeldSale) -> dict:
    return {
        "id": row.id,
        "label": row.label,
        "store_id": row.store_id,
        "user_id": row.user_id,
        "cart": row.cart or {},
        "item_count": int(row.item_count or 0),
        "total": money_json(row.total),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def hold_sale(
    db: AsyncSession, *, tenant_id: str, user_id: str | None, store_id: str | None, label: str, cart: dict
) -> m.PosHeldSale:
    items = cart.get("items") if isinstance(cart, dict) else None
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=422, detail="There is nothing in the cart to hold")
    if len(items) > 300:
        raise HTTPException(status_code=422, detail="That cart is too big to hold")
    count = await db.scalar(select(func.count()).select_from(m.PosHeldSale).where(m.PosHeldSale.tenant_id == tenant_id))
    if int(count or 0) >= 200:
        raise HTTPException(status_code=409, detail="200 sales are on hold already. Finish or clear some first.")
    total = 0.0
    qty = 0
    for item in items:
        try:
            q = float(item.get("quantity") or 0)
            total += q * float(item.get("unit_price") or 0)
            qty += 1
        except (TypeError, ValueError, AttributeError):
            raise HTTPException(status_code=422, detail="A held cart line is not readable") from None
    row = m.PosHeldSale(
        tenant_id=tenant_id,
        store_id=store_id,
        user_id=user_id,
        label=require_honest_narrative(label, label="label", max_length=120),
        cart=cart,
        item_count=qty,
        total=money_json(round(total, 2)),
    )
    db.add(row)
    await db.flush()
    return row


async def list_held(db: AsyncSession, *, tenant_id: str, store_id: str | None = None) -> list[m.PosHeldSale]:
    stmt = select(m.PosHeldSale).where(m.PosHeldSale.tenant_id == tenant_id).order_by(m.PosHeldSale.created_at.desc())
    if store_id:
        stmt = stmt.where(m.PosHeldSale.store_id == store_id)
    return list((await db.execute(stmt.limit(200))).scalars())


async def take_held(db: AsyncSession, *, tenant_id: str, held_id: str) -> m.PosHeldSale:
    """Pick a held cart back up: it leaves the hold list so it cannot be rung twice."""
    row = (
        await db.execute(select(m.PosHeldSale).where(m.PosHeldSale.id == held_id, m.PosHeldSale.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="That held sale was already picked up or cleared")
    await db.delete(row)
    await db.flush()
    return row


# --- layaway ---------------------------------------------------------------------------------------


def serialize_layaway(row: m.PosLayaway, payments: list[m.PosLayawayPayment] | None = None) -> dict:
    total = money_json(row.total)
    paid = money_json(row.paid)
    out = {
        "id": row.id,
        "layaway_number": row.layaway_number,
        "store_id": row.store_id,
        "customer_id": row.customer_id,
        "customer_name": row.customer_name,
        "phone": row.phone,
        "items": row.items or [],
        "subtotal": money_json(row.subtotal),
        "tax": money_json(row.tax),
        "total": total,
        "paid": paid,
        "balance": money_json(round(total - paid, 2)),
        "status": row.status,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }
    if payments is not None:
        out["payments"] = [
            {
                "id": p.id,
                "method": p.method,
                "amount": money_json(p.amount),
                "reference": p.reference,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ]
    return out


async def _next_layaway_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    count = await db.scalar(
        select(func.count()).select_from(m.PosLayaway).where(m.PosLayaway.tenant_id == tenant_id)
    )
    return f"LAY-{year}-{int(count or 0) + 1:04d}"


async def _layaway(db: AsyncSession, tenant_id: str, layaway_id: str, *, lock: bool = False) -> m.PosLayaway:
    stmt = select(m.PosLayaway).where(m.PosLayaway.id == layaway_id, m.PosLayaway.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Layaway not found")
    return row


async def layaway_payments(db: AsyncSession, tenant_id: str, layaway_id: str) -> list[m.PosLayawayPayment]:
    return list(
        (
            await db.execute(
                select(m.PosLayawayPayment)
                .where(m.PosLayawayPayment.tenant_id == tenant_id, m.PosLayawayPayment.layaway_id == layaway_id)
                .order_by(m.PosLayawayPayment.created_at)
            )
        ).scalars()
    )


async def _warehouse(db: AsyncSession, tenant_id: str, store_id: str | None) -> str | None:
    if not store_id:
        return None
    from app.stores import warehouse_for_store

    try:
        return (await warehouse_for_store(db, tenant_id, store_id)).id
    except HTTPException:
        return None


async def open_layaway(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    store_id: str | None,
    customer_id: str | None,
    customer_name: str | None,
    phone: str | None,
    items: list[dict],
    due_date: date | None,
    notes: str | None,
    deposit: float = 0,
    deposit_method: str = "cash",
    deposit_reference: str | None = None,
) -> m.PosLayaway:
    from app import inventory as inventory_svc
    from app import tax as tax_svc

    if not items:
        raise HTTPException(status_code=422, detail="Add the goods to set aside")
    name = (customer_name or "").strip()
    if customer_id:
        party = await db.get(m.Party, customer_id)
        if party is None or party.tenant_id != tenant_id or party.kind != "customer":
            raise HTTPException(status_code=404, detail="Customer not found")
        name = name or party.name
        phone = phone or party.phone
    if not name:
        raise HTTPException(status_code=422, detail="Whose layaway is it? Add the customer's name")
    if not (phone or "").strip():
        raise HTTPException(status_code=422, detail="Add the customer's phone so you can reach them")
    warehouse_id = await _warehouse(db, tenant_id, store_id)
    lines: list[dict] = []
    subtotal = tax_total = 0.0
    number = await _next_layaway_number(db, tenant_id)
    for item in items:
        product = await db.get(m.Product, str(item.get("product_id")))
        if product is None or product.tenant_id != tenant_id or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")
        qty = money_json(item.get("quantity") or 0)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Each line needs a quantity")
        price = money_json(product.selling_price or 0)
        gross = money_json(round(qty * price, 2))
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        net, tax, total = spec.compute_amounts(gross)
        subtotal += money_json(net)
        tax_total += money_json(tax)
        lines.append(
            {
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "quantity": qty,
                "unit_price": price,
                "net": money_json(net),
                "tax": money_json(tax),
                "total": money_json(total),
            }
        )
        # Set aside: out of sale stock now, so nobody else can buy it.
        await inventory_svc.apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=product.id,
            quantity_delta=-qty,
            movement_type="stock_out",
            user_id=user_id,
            reference_type="layaway",
            reference_id=number,
            notes=f"Set aside on layaway {number}",
            warehouse_id=warehouse_id,
        )
    total = money_json(round(subtotal + tax_total, 2))
    row = m.PosLayaway(
        tenant_id=tenant_id,
        layaway_number=number,
        store_id=store_id,
        warehouse_id=warehouse_id,
        customer_id=customer_id,
        customer_name=name[:180],
        phone=(phone or "").strip()[:50],
        items=lines,
        subtotal=money_json(round(subtotal, 2)),
        tax=money_json(round(tax_total, 2)),
        total=total,
        paid=0,
        status="open",
        due_date=due_date,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if money_json(deposit) > 0:
        await pay_layaway(
            db, tenant_id=tenant_id, layaway_id=row.id, amount=deposit, method=deposit_method,
            reference=deposit_reference, user_id=user_id,
        )
    return row


async def pay_layaway(
    db: AsyncSession,
    *,
    tenant_id: str,
    layaway_id: str,
    amount: float,
    method: str,
    reference: str | None,
    user_id: str | None,
) -> m.PosLayaway:
    row = await _layaway(db, tenant_id, layaway_id, lock=True)
    if row.status != "open":
        raise HTTPException(status_code=409, detail=f"This layaway is {row.status}")
    amt = money_json(amount)
    balance = money_json(round(money_json(row.total) - money_json(row.paid), 2))
    if amt <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount paid")
    if amt > balance + 0.009:
        raise HTTPException(status_code=422, detail=f"Only {balance:.2f} is left to pay")
    key = (method or "cash").strip().lower()
    if key not in LAYAWAY_METHODS:
        raise HTTPException(status_code=422, detail="Pay by cash, card, Mobile Money, bank transfer or wallet")
    if reference and str(reference).startswith("till_"):
        from app import till_payments

        await till_payments.claim(db, tenant_id=tenant_id, reference=str(reference), amount=amt, used_ref=row.layaway_number)
    await accounting.ensure_default_accounts(db, tenant_id)
    cash_code, _ = accounting.liquid_gl_for_payment_method(key)
    description = f"Layaway {row.layaway_number} payment ({key})"
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=[
            {"account_code": cash_code, "debit": amt, "credit": 0, "description": description},
            {"account_code": DEPOSITS, "debit": 0, "credit": amt, "description": description},
        ],
        reference=row.layaway_number,
        source_type="pos_layaway_payment",
        source_id=row.id,
    )
    db.add(
        m.PosLayawayPayment(
            tenant_id=tenant_id,
            layaway_id=row.id,
            method=key,
            amount=amt,
            reference=(str(reference).strip()[:100] if reference else None),
            journal_entry_id=entry.id,
            created_by=user_id,
        )
    )
    row.paid = money_json(round(money_json(row.paid) + amt, 2))
    await db.flush()
    if money_json(row.paid) + 0.009 >= money_json(row.total):
        await _complete_layaway(db, row, user_id=user_id)
    return row


async def _complete_layaway(db: AsyncSession, row: m.PosLayaway, *, user_id: str | None) -> None:
    """Paid in full: the customer collects, and the sale is booked from the money held."""
    description = f"Layaway {row.layaway_number} collected"
    total = money_json(row.total)
    tax = money_json(row.tax)
    net = money_json(round(total - tax, 2))
    lines = [{"account_code": DEPOSITS, "debit": total, "credit": 0, "description": description}]
    if net > 0:
        lines.append({"account_code": "4000", "debit": 0, "credit": net, "description": description})
    if tax > 0:
        lines.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    cogs = await accounting.compute_standard_cogs(
        db,
        tenant_id=row.tenant_id,
        lines=[{"product_id": i["product_id"], "quantity": i["quantity"]} for i in (row.items or [])],
    )
    accounting.append_cogs_lines(lines, cogs, reverse=False)
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=row.tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=row.layaway_number,
        source_type="pos_layaway",
        source_id=row.id,
    )
    row.journal_entry_id = entry.id
    row.status = "completed"
    row.closed_at = datetime.utcnow()
    await db.flush()


async def cancel_layaway(
    db: AsyncSession,
    *,
    tenant_id: str,
    layaway_id: str,
    keep: float,
    refund_method: str,
    reason: str,
    user_id: str | None,
) -> m.PosLayaway:
    """Goods go back on sale. The money held is refunded, less any fee kept (with a reason)."""
    from app import inventory as inventory_svc

    row = await _layaway(db, tenant_id, layaway_id, lock=True)
    if row.status != "open":
        raise HTTPException(status_code=409, detail=f"This layaway is {row.status}")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    paid = money_json(row.paid)
    fee = money_json(keep or 0)
    if fee < 0 or fee > paid + 0.009:
        raise HTTPException(status_code=422, detail=f"You can keep up to the {paid:.2f} paid")
    refund = money_json(round(paid - fee, 2))
    for item in row.items or []:
        await inventory_svc.apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=item["product_id"],
            quantity_delta=money_json(item["quantity"]),
            movement_type="stock_in",
            user_id=user_id,
            reference_type="layaway_cancel",
            reference_id=row.layaway_number,
            notes=f"Layaway {row.layaway_number} cancelled: back on sale",
            warehouse_id=row.warehouse_id,
        )
    if paid > 0:
        await accounting.ensure_default_accounts(db, tenant_id)
        description = f"Layaway {row.layaway_number} cancelled: {why}"[:255]
        lines = [{"account_code": DEPOSITS, "debit": paid, "credit": 0, "description": description}]
        if refund > 0:
            code, _ = accounting.liquid_gl_for_payment_method((refund_method or "cash").strip().lower())
            lines.append({"account_code": code, "debit": 0, "credit": refund, "description": description})
        if fee > 0:
            lines.append({"account_code": "4400", "debit": 0, "credit": fee, "description": description})
        await accounting.post_journal_entry(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            description=description,
            lines=lines,
            reference=row.layaway_number,
            source_type="pos_layaway_cancel",
            source_id=row.id,
        )
    row.status = "cancelled"
    row.closed_at = datetime.utcnow()
    row.notes = f"{(row.notes + ' ') if row.notes else ''}Cancelled: {why}. Refunded {refund:.2f}, kept {fee:.2f}."[:1000]
    await db.flush()
    return row


async def list_layaways(db: AsyncSession, *, tenant_id: str, status: str | None = None) -> list[m.PosLayaway]:
    stmt = select(m.PosLayaway).where(m.PosLayaway.tenant_id == tenant_id).order_by(m.PosLayaway.created_at.desc())
    if status:
        stmt = stmt.where(m.PosLayaway.status == status)
    return list((await db.execute(stmt.limit(500))).scalars())


# --- serial numbers ----------------------------------------------------------------------------


def clean_serials(raw) -> list[str]:
    out: list[str] = []
    for value in raw or []:
        text = " ".join(str(value or "").split()).upper()
        if not text:
            continue
        if len(text) > 80 or not any(ch.isalnum() for ch in text):
            raise HTTPException(status_code=422, detail=f"'{text[:20]}' is not a serial number")
        if text in out:
            raise HTTPException(status_code=422, detail=f"Serial {text} is listed twice")
        out.append(text)
    return out


async def receive_serials(
    db: AsyncSession, *, tenant_id: str, product: m.Product, serials: list[str], warehouse_id: str | None, ref: str | None
) -> list[m.ProductSerial]:
    """Units coming in. A serial already in stock is refused; one that came back is put back in stock."""
    rows: list[m.ProductSerial] = []
    for serial in clean_serials(serials):
        row = (
            await db.execute(
                select(m.ProductSerial).where(
                    m.ProductSerial.tenant_id == tenant_id,
                    m.ProductSerial.product_id == product.id,
                    m.ProductSerial.serial == serial,
                )
            )
        ).scalar_one_or_none()
        if row is not None and row.status == "in_stock":
            raise HTTPException(status_code=409, detail=f"Serial {serial} is already in stock")
        if row is None:
            row = m.ProductSerial(tenant_id=tenant_id, product_id=product.id, serial=serial)
            db.add(row)
        row.status = "in_stock"
        row.warehouse_id = warehouse_id
        row.received_ref = (ref or "")[:80] or None
        row.sold_ref = None
        row.sold_at = None
        rows.append(row)
    await db.flush()
    return rows


async def sell_serials(
    db: AsyncSession, *, tenant_id: str, product: m.Product, serials: list[str], quantity: float, sale_ref: str
) -> None:
    """A serial-tracked product is sold unit by unit: one in-stock serial per unit."""
    picked = clean_serials(serials)
    if len(picked) != int(round(float(quantity))) or abs(float(quantity) - round(float(quantity))) > 1e-9:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SERIALS_REQUIRED",
                "message": f"{product.name} needs one serial number for each unit sold ({int(round(float(quantity)))}).",
            },
        )
    for serial in picked:
        row = (
            await db.execute(
                select(m.ProductSerial).where(
                    m.ProductSerial.tenant_id == tenant_id,
                    m.ProductSerial.product_id == product.id,
                    m.ProductSerial.serial == serial,
                )
            )
        ).scalar_one_or_none()
        if row is None or row.status != "in_stock":
            raise HTTPException(status_code=409, detail=f"Serial {serial} of {product.name} is not in stock")
        row.status = "sold"
        row.sold_ref = sale_ref[:80]
        row.sold_at = datetime.utcnow()
    await db.flush()


async def return_serials(
    db: AsyncSession,
    *,
    tenant_id: str,
    product: m.Product,
    serials: list[str],
    quantity: float,
    sale_ref: str,
    return_ref: str,
    back_in_stock: bool,
) -> None:
    """Units coming back from a sale: they must be the serials that sale sold, one per unit returned."""
    picked = clean_serials(serials)
    if len(picked) != int(round(float(quantity))):
        raise HTTPException(
            status_code=422,
            detail={"code": "SERIALS_REQUIRED", "message": f"Enter the serial of each {product.name} coming back."},
        )
    for serial in picked:
        row = (
            await db.execute(
                select(m.ProductSerial).where(
                    m.ProductSerial.tenant_id == tenant_id,
                    m.ProductSerial.product_id == product.id,
                    m.ProductSerial.serial == serial,
                )
            )
        ).scalar_one_or_none()
        if row is None or row.status != "sold" or (row.sold_ref or "") != sale_ref:
            raise HTTPException(status_code=409, detail=f"Serial {serial} was not sold on this receipt")
        # Fit to sell goes back in stock; damaged stays out, marked returned.
        row.status = "in_stock" if back_in_stock else "returned"
        row.received_ref = return_ref[:80]
        if back_in_stock:
            row.sold_ref = None
            row.sold_at = None
    await db.flush()


def serialize_serial(row: m.ProductSerial, product_name: str | None = None) -> dict:
    return {
        "id": row.id,
        "product_id": row.product_id,
        "product_name": product_name,
        "serial": row.serial,
        "status": row.status,
        "warehouse_id": row.warehouse_id,
        "received_ref": row.received_ref,
        "sold_ref": row.sold_ref,
        "sold_at": row.sold_at.isoformat() if row.sold_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def find_serials(
    db: AsyncSession, *, tenant_id: str, q: str | None = None, product_id: str | None = None, status: str | None = None
) -> list[tuple[m.ProductSerial, str]]:
    stmt = (
        select(m.ProductSerial, m.Product.name)
        .join(m.Product, m.Product.id == m.ProductSerial.product_id)
        .where(m.ProductSerial.tenant_id == tenant_id)
        .order_by(m.ProductSerial.created_at.desc())
    )
    if q:
        stmt = stmt.where(m.ProductSerial.serial.ilike(f"%{q.strip().upper()}%"))
    if product_id:
        stmt = stmt.where(m.ProductSerial.product_id == product_id)
    if status:
        stmt = stmt.where(m.ProductSerial.status == status)
    return [(r[0], r[1]) for r in (await db.execute(stmt.limit(300))).all()]
