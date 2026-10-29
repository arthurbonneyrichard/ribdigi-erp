"""Till returns (BR-7.5 / BR-8): take items back against a till receipt and refund.

A till sale has no sales invoice, so it is returned here rather than through
``sales_docs.create_return``. The return is created and posted in one step:
stock goes back to the store's warehouse (unless the item is not fit to sell),
the sale is reversed in the books, and the refund is paid the chosen way. A cash
refund is also recorded as a drawer cash-out on the open shift, so the cash count
stays right. A customer on the receipt can take store credit instead.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.doc_numbers import next_credit_note_number, next_sales_return_number
from app.honesty import money_json, optional_honest_narrative
from app.sales_docs import RETURN_REASONS

REFUND_METHODS = frozenset({"cash", "card", "mobile_money", "bank_transfer", "store_credit"})


def _line_key(product_id: str | None, variant_id: str | None) -> tuple[str, str | None]:
    return (str(product_id or ""), variant_id or None)


async def get_till_sale(db: AsyncSession, tenant_id: str, sale_id: str) -> m.Transaction:
    sale = await db.get(m.Transaction, sale_id)
    if sale is None or sale.tenant_id != tenant_id or sale.tx_type != "pos_sale":
        raise HTTPException(status_code=404, detail="Till receipt not found")
    return sale


async def returned_qty_by_line(
    db: AsyncSession, tenant_id: str, sale_id: str
) -> dict[tuple[str, str | None], float]:
    rows = (
        await db.execute(
            select(m.SalesReturnItem.product_id, m.SalesReturnItem.variant_id, m.SalesReturnItem.quantity)
            .join(m.SalesReturn, m.SalesReturn.id == m.SalesReturnItem.sales_return_id)
            .where(
                m.SalesReturn.tenant_id == tenant_id,
                m.SalesReturn.transaction_id == sale_id,
                m.SalesReturn.status != "cancelled",
            )
        )
    ).all()
    out: dict[tuple[str, str | None], float] = {}
    for pid, vid, qty in rows:
        key = _line_key(pid, vid)
        out[key] = money_json(round(out.get(key, 0.0) + money_json(qty or 0), 3))
    return out


def _sale_payment_method(sale: m.Transaction) -> str:
    payload = sale.payload or {}
    payments = payload.get("payments") or []
    if len(payments) == 1:
        return str(payments[0].get("payment_method") or "cash")
    return str(payload.get("payment_method") or "cash")


async def returnable_lines(db: AsyncSession, tenant_id: str, sale: m.Transaction) -> list[dict]:
    """Receipt lines with what can still be returned and the refund per unit.

    The refund per unit is what the customer actually paid for it: the line total
    after line discount, scaled by any cart discount on the receipt.
    """
    payload = sale.payload or {}
    items = payload.get("items") or []
    gross = sum(money_json(i.get("line_total") or 0) for i in items)
    factor = money_json(sale.total or 0) / gross if gross > 0 else 1.0
    already = await returned_qty_by_line(db, tenant_id, sale.id)
    lines = []
    for item in items:
        qty = money_json(item.get("quantity") or 0)
        if qty <= 0:
            continue
        key = _line_key(item.get("product_id"), item.get("variant_id"))
        returned = already.get(key, 0.0)
        line_total = money_json(item.get("line_total") or 0) * factor
        line_sub = money_json(item.get("line_subtotal") or 0) * factor
        lines.append(
            {
                "product_id": key[0],
                "variant_id": key[1],
                "unit_id": item.get("unit_id"),
                "name": item.get("name"),
                "sku": item.get("sku"),
                "quantity": qty,
                "returned_quantity": returned,
                "returnable_quantity": money_json(round(max(qty - returned, 0.0), 3)),
                "unit_refund": money_json(round(line_total / qty, 2)),
                "unit_net": line_sub / qty,
                "tax_rate": money_json(item.get("tax_rate") or 0),
            }
        )
    return lines


async def serialize_till_receipt(db: AsyncSession, tenant_id: str, sale: m.Transaction) -> dict:
    payload = sale.payload or {}
    customer_name = payload.get("customer_name")
    if sale.party_id and not customer_name:
        party = await db.get(m.Party, sale.party_id)
        customer_name = party.name if party else None
    lines = await returnable_lines(db, tenant_id, sale)
    return {
        "id": sale.id,
        "reference": sale.reference,
        "created_at": sale.created_at,
        "total": money_json(sale.total or 0),
        "payment_method": _sale_payment_method(sale),
        "customer_id": sale.party_id,
        "customer_name": customer_name or "Walk-in",
        "lines": lines,
        "fully_returned": all(line["returnable_quantity"] <= 0 for line in lines),
    }


async def find_till_receipts(
    db: AsyncSession, tenant_id: str, *, q: str | None = None, limit: int = 20
) -> list[m.Transaction]:
    stmt = (
        select(m.Transaction)
        .where(m.Transaction.tenant_id == tenant_id, m.Transaction.tx_type == "pos_sale")
        .order_by(m.Transaction.created_at.desc())
        .limit(limit)
    )
    text = (q or "").strip()
    if text:
        stmt = stmt.where(m.Transaction.reference.ilike(f"%{text}%"))
    return list((await db.execute(stmt)).scalars().all())


async def create_till_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sale_id: str,
    items: list[dict],
    reason: str,
    refund_method: str | None = None,
    notes: str | None = None,
) -> m.SalesReturn:
    from app import pos as pos_svc
    from app import stores as stores_svc
    from app.accounting import post_sales_return_journal, post_sales_return_refund_journal
    from app.inventory import apply_line_items_stock

    if reason not in RETURN_REASONS:
        raise HTTPException(status_code=400, detail=f"reason must be one of {sorted(RETURN_REASONS)}")
    sale = await get_till_sale(db, tenant_id, sale_id)
    if not items:
        raise HTTPException(status_code=400, detail="Choose at least one item to return")

    by_key = {_line_key(line["product_id"], line["variant_id"]): line for line in await returnable_lines(db, tenant_id, sale)}
    prepared: list[dict] = []
    subtotal = 0.0
    total = 0.0
    for item in items:
        key = _line_key(item.get("product_id"), item.get("variant_id"))
        line = by_key.get(key)
        if line is None and key[1] is None:
            matches = [v for (pid, _), v in by_key.items() if pid == key[0]]
            line = matches[0] if len(matches) == 1 else None
        if line is None:
            raise HTTPException(status_code=400, detail="That item is not on this receipt")
        qty = money_json(item.get("quantity") or 0)
        if qty <= 0 or qty > line["returnable_quantity"] + 1e-9:
            raise HTTPException(
                status_code=400,
                detail=f"You can return at most {line['returnable_quantity']:g} of {line.get('name') or 'this item'}",
            )
        sellable = bool(item.get("restock", True))
        line_total = money_json(round(line["unit_refund"] * qty, 2))
        line_net = money_json(round(line["unit_net"] * qty, 2))
        subtotal += line_net
        total += line_total
        prepared.append(
            {
                "product_id": line["product_id"],
                "variant_id": line["variant_id"],
                "unit_id": line["unit_id"],
                "quantity": qty,
                "unit_price": line["unit_refund"],
                "tax_rate": line["tax_rate"],
                "line_total": line_total,
                "condition": "sellable" if sellable else "discard",
            }
        )
    subtotal = money_json(round(subtotal, 2))
    total = money_json(round(total, 2))

    method = (refund_method or "").strip().lower() or _sale_payment_method(sale)
    if method not in REFUND_METHODS:
        # Credit, gift card and other tenders refund as store credit for a known customer.
        method = "store_credit" if sale.party_id else "cash"
    if method == "store_credit" and not sale.party_id:
        raise HTTPException(status_code=400, detail="Store credit needs a customer on the receipt")

    session = None
    if method == "cash":
        session = (
            await db.execute(
                select(m.PosSession).where(
                    m.PosSession.tenant_id == tenant_id,
                    m.PosSession.user_id == user_id,
                    m.PosSession.status == "open",
                )
            )
        ).scalars().first()
        if session is None:
            raise HTTPException(status_code=409, detail="Open your till shift before giving a cash refund")

    origin = await db.get(m.PosSession, sale.session_id) if sale.session_id else None
    store_id = (session.store_id if session else None) or (origin.store_id if origin else None)

    ret = m.SalesReturn(
        tenant_id=tenant_id,
        return_number=await next_sales_return_number(db, tenant_id),
        customer_id=sale.party_id,
        sales_invoice_id=None,
        transaction_id=sale.id,
        session_id=session.id if session else None,
        store_id=store_id,
        status="posted",
        reason=reason,
        restock=any(p["condition"] == "sellable" for p in prepared),
        subtotal=subtotal,
        tax_amount=money_json(round(total - subtotal, 2)),
        total_amount=total,
        notes=optional_honest_narrative(notes, label="sales return notes"),
        created_by=user_id,
        posted_at=datetime.utcnow(),
    )
    ret.credit_note_number = await next_credit_note_number(db, tenant_id)
    db.add(ret)
    await db.flush()
    for line in prepared:
        db.add(
            m.SalesReturnItem(
                tenant_id=tenant_id,
                sales_return_id=ret.id,
                **{k: v for k, v in line.items() if k != "unit_id"},
            )
        )
    await db.flush()

    restock_items = [
        {k: line[k] for k in ("product_id", "variant_id", "unit_id", "quantity")}
        for line in prepared
        if line["condition"] == "sellable"
    ]
    if restock_items:
        warehouse_id = None
        receipt_store_id = origin.store_id if origin else None
        if receipt_store_id:
            warehouse_id = (await stores_svc.warehouse_for_store(db, tenant_id, receipt_store_id)).id
        await apply_line_items_stock(
            db,
            tenant_id=tenant_id,
            items=restock_items,
            movement_type="stock_in",
            user_id=user_id,
            reference_type="sales_return",
            reference_id=ret.id,
            outbound=False,
            warehouse_id=warehouse_id,
        )
    for line in prepared:
        if line["condition"] != "sellable":
            db.add(
                m.AuditLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="return_discarded",
                    entity="sales_return",
                    entity_id=ret.id,
                    details={"product_id": line["product_id"], "quantity": line["quantity"]},
                )
            )

    # Reverse the sale (revenue, tax, cost of goods for restocked items) against AR,
    # then pay that credit out, or leave it as the customer's store credit.
    await post_sales_return_journal(db, tenant_id=tenant_id, user_id=user_id, sales_return=ret)
    if method == "store_credit":
        party = await db.get(m.Party, sale.party_id)
        if party is not None:
            party.balance = money_json(round(money_json(party.balance or 0) - total, 2))
        ret.settlement_method = "adjust"
        ret.refunded_amount = 0
    else:
        await post_sales_return_refund_journal(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            sales_return=ret,
            amount=total,
            payment_method=method,
        )
        ret.settlement_method = "refund"
        ret.refund_payment_method = method
        ret.refunded_amount = total
        if session is not None:
            await pos_svc.record_cash_movement(
                db,
                session=session,
                user_id=user_id,
                movement_type="cash_out",
                amount=total,
                reason=f"Refund {ret.return_number} for {sale.reference}",
            )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="sales_return_posted",
            entity="sales_return",
            entity_id=ret.id,
            details={
                "return_number": ret.return_number,
                "credit_note_number": ret.credit_note_number,
                "till_receipt": sale.reference,
                "total_amount": total,
                "refund_method": method,
            },
        )
    )
    await db.flush()
    return ret
