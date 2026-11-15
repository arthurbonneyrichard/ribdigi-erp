"""Bakery trade: shops, hotels and schools supplied on account, and the suppliers the bakery owes.

Trade customers
- A standing order is the same delivery on set days. "Make today's trade deliveries" turns
  every standing order due today into one invoice per customer (once a day per customer).
- An invoice takes the goods out of stock and books the sale on credit: debit 1100 Accounts
  Receivable, credit sales and VAT, plus cost of goods. Prices are the shop price less the
  customer's trade discount.
- A customer over their credit limit is refused unless a manager says to go ahead.
- A payment clears the oldest invoices first. Cash goes into the open till.
- A statement shows the opening balance, invoices and payments in the period, and what is owed by age.

Suppliers
- Stock bought on credit is owed to a supplier (2000 Accounts Payable). A payment clears it
  (debit 2000, credit the money account); cash can come out of the till.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import bakery as core
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

PAY_METHODS = frozenset({"cash", "card", "mobile_money", "bank_transfer"})
MANAGERS = frozenset({"bakery_manager", "company_admin", "super_admin"})
_money = core._money
_qty = core._qty


def _pay_method(value: str | None) -> str:
    key = (value or "").strip().lower()
    if key not in PAY_METHODS:
        raise HTTPException(status_code=422, detail="Choose cash, card, Mobile Money or bank transfer")
    return key


def _days(value: str | None) -> str:
    days = (value or "").strip()
    if len(days) != 7 or set(days) - {"0", "1"} or "1" not in days:
        raise HTTPException(status_code=422, detail="Choose at least one day, Monday to Sunday")
    return days


# --- Customers ---------------------------------------------------------------------------


async def _customer(db: AsyncSession, tenant_id: str, customer_id: str, *, lock: bool = False) -> m.BakeryCustomer:
    stmt = select(m.BakeryCustomer).where(m.BakeryCustomer.id == customer_id, m.BakeryCustomer.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


async def balance(db: AsyncSession, tenant_id: str, customer_id: str) -> float:
    owed = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakeryInvoice.total - m.BakeryInvoice.paid), 0)).where(
                m.BakeryInvoice.tenant_id == tenant_id,
                m.BakeryInvoice.customer_id == customer_id,
                m.BakeryInvoice.status.in_(("open", "part_paid")),
            )
        )
    ).scalar_one()
    return _money(owed)


async def save_customer(db: AsyncSession, tenant_id: str, payload, *, customer_id: str | None = None) -> m.BakeryCustomer:
    data = payload.model_dump(exclude_unset=True)
    if customer_id:
        row = await _customer(db, tenant_id, customer_id)
    else:
        row = m.BakeryCustomer(tenant_id=tenant_id, name="")
        db.add(row)
    if "name" in data or not customer_id:
        name = require_honest_narrative(data.get("name"), label="customer name", max_length=180)
        clash = (
            await db.execute(
                select(m.BakeryCustomer.id).where(
                    m.BakeryCustomer.tenant_id == tenant_id,
                    func.lower(m.BakeryCustomer.name) == name.lower(),
                    m.BakeryCustomer.id != (customer_id or ""),
                )
            )
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="A customer with this name already exists")
        row.name = name
    if "phone" in data:
        row.phone = data["phone"]
    if "address" in data:
        row.address = optional_honest_narrative(data["address"], label="address", max_length=500)
    for key in ("credit_limit", "trade_discount_pct", "terms_days", "is_active"):
        if key in data and data[key] is not None:
            setattr(row, key, data[key])
    await db.flush()
    return row


async def present_customer(db: AsyncSession, tenant_id: str, row: m.BakeryCustomer, *, today: date) -> dict:
    owed = await balance(db, tenant_id, row.id)
    overdue = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakeryInvoice.total - m.BakeryInvoice.paid), 0)).where(
                m.BakeryInvoice.tenant_id == tenant_id,
                m.BakeryInvoice.customer_id == row.id,
                m.BakeryInvoice.status.in_(("open", "part_paid")),
                m.BakeryInvoice.due_date < today,
            )
        )
    ).scalar_one()
    standing = (
        await db.execute(
            select(m.BakeryStandingOrder, m.Product.name)
            .join(m.Product, m.Product.id == m.BakeryStandingOrder.product_id)
            .where(m.BakeryStandingOrder.customer_id == row.id, m.BakeryStandingOrder.is_active.is_(True))
        )
    ).all()
    limit = _money(row.credit_limit)
    return {
        "id": row.id,
        "name": row.name,
        "phone": row.phone,
        "address": row.address,
        "credit_limit": limit,
        "trade_discount_pct": money_json(row.trade_discount_pct or 0),
        "terms_days": int(row.terms_days or 0),
        "is_active": bool(row.is_active),
        "balance": owed,
        "overdue": _money(overdue),
        "available_credit": _money(limit - owed) if limit > 0 else None,
        "standing_orders": [
            {"id": s.id, "product_id": s.product_id, "name": name, "quantity": _qty(s.quantity), "days": s.days}
            for s, name in standing
        ],
    }


async def list_customers(db: AsyncSession, tenant_id: str, *, today: date) -> list[dict]:
    rows = (
        await db.execute(
            select(m.BakeryCustomer).where(m.BakeryCustomer.tenant_id == tenant_id).order_by(m.BakeryCustomer.name.asc())
        )
    ).scalars().all()
    return [await present_customer(db, tenant_id, row, today=today) for row in rows]


async def save_standing(db: AsyncSession, tenant_id: str, customer_id: str, payload) -> m.BakeryStandingOrder:
    await _customer(db, tenant_id, customer_id)
    await core._product(db, tenant_id, payload.product_id)
    row = (
        await db.execute(
            select(m.BakeryStandingOrder).where(
                m.BakeryStandingOrder.customer_id == customer_id,
                m.BakeryStandingOrder.product_id == payload.product_id,
                m.BakeryStandingOrder.is_active.is_(True),
            )
        )
    ).scalars().first()
    if row is None:
        row = m.BakeryStandingOrder(tenant_id=tenant_id, customer_id=customer_id, product_id=payload.product_id)
        db.add(row)
    row.quantity = _qty(payload.quantity)
    row.days = _days(payload.days)
    await db.flush()
    return row


async def stop_standing(db: AsyncSession, tenant_id: str, standing_id: str) -> None:
    row = await db.get(m.BakeryStandingOrder, standing_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Standing order not found")
    row.is_active = False
    await db.flush()


# --- Invoices ----------------------------------------------------------------------------


class _Line:
    def __init__(self, product_id: str, quantity: float, discount_percent: float | None):
        self.product_id = product_id
        self.quantity = quantity
        self.discount_percent = discount_percent


async def create_invoice(
    db: AsyncSession,
    tenant_id: str,
    customer_id: str,
    lines,
    *,
    user_id,
    role: str = "",
    invoice_date: date | None = None,
    notes: str | None = None,
    from_standing: bool = False,
    override_limit: bool = False,
) -> m.BakeryInvoice:
    customer = await _customer(db, tenant_id, customer_id, lock=True)
    if not customer.is_active:
        raise HTTPException(status_code=409, detail="This customer is switched off")
    day = invoice_date or await core.bakery_today(db, tenant_id)
    trade = float(customer.trade_discount_pct or 0)
    priced_in = [_Line(str(x.product_id), float(x.quantity), trade or None) for x in lines]
    priced, net, tax, gross = await core._priced_lines(db, tenant_id, priced_in, max_discount=None)
    limit = _money(customer.credit_limit)
    if limit > 0:
        owed = await balance(db, tenant_id, customer.id)
        if owed + gross > limit + 0.004:
            if not (override_limit and role in MANAGERS):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "CREDIT_LIMIT",
                        "message": f"{customer.name} owes {owed:.2f}; this invoice takes them past their {limit:.2f} limit",
                    },
                )
    row = m.BakeryInvoice(
        tenant_id=tenant_id,
        invoice_number=await core._next_number(db, tenant_id, m.BakeryInvoice, "BI"),
        customer_id=customer.id,
        invoice_date=day,
        due_date=day + timedelta(days=int(customer.terms_days or 0)),
        status="open",
        from_standing=from_standing,
        subtotal=net,
        tax=tax,
        total=gross,
        paid=0,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    for line in priced:
        db.add(
            m.BakeryInvoiceLine(
                tenant_id=tenant_id, invoice_id=row.id, product_id=line["product"].id, name=line["product"].name,
                quantity=line["quantity"], unit_price=_money(float(line["line_total"] - line["tax"]) / line["quantity"]),
                tax=line["tax"], line_total=line["line_total"], unit_cost=_money(line["product"].cost_price),
            )
        )
    row.cost_of_goods = await core._take_stock(
        db, tenant_id, priced, user_id=user_id, reference=row.id, number=row.invoice_number
    )
    description = f"Bakery trade invoice {row.invoice_number} {customer.name}"[:255]
    journal = [
        {"account_code": "1100", "debit": gross, "credit": 0, "description": description},
        {"account_code": "4000", "debit": 0, "credit": _money(gross - tax), "description": description},
    ]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    core.accounting.append_cogs_lines(journal, row.cost_of_goods)
    row.journal_entry_id = await core._post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=row.invoice_number, source="bakery_invoice", source_id=row.id,
    )
    await core._audit(
        db, tenant_id, user_id, "bakery_invoice", "bakery_invoice", row.id,
        {"invoice_number": row.invoice_number, "customer": customer.name, "total": gross, "over_limit_by_manager": override_limit},
    )
    await db.flush()
    return row


async def void_invoice(db: AsyncSession, tenant_id: str, invoice_id: str, *, reason: str, restock: bool, user_id) -> m.BakeryInvoice:
    row = (
        await db.execute(
            select(m.BakeryInvoice).where(m.BakeryInvoice.id == invoice_id, m.BakeryInvoice.tenant_id == tenant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if row.status == "void":
        raise HTTPException(status_code=409, detail="This invoice is already void")
    if float(row.paid or 0) > 0:
        raise HTTPException(status_code=409, detail="Money has been paid on this invoice. It cannot be voided.")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    gross, tax = _money(row.total), _money(row.tax)
    description = f"Bakery trade invoice {row.invoice_number} void"
    journal = [
        {"account_code": "4000", "debit": _money(gross - tax), "credit": 0, "description": description},
        {"account_code": "1100", "debit": 0, "credit": gross, "description": description},
    ]
    if tax > 0:
        journal.insert(1, {"account_code": "2100", "debit": tax, "credit": 0, "description": description})
    if restock:
        core.accounting.append_cogs_lines(journal, _money(row.cost_of_goods), reverse=True)
        for line in (await db.execute(select(m.BakeryInvoiceLine).where(m.BakeryInvoiceLine.invoice_id == row.id))).scalars():
            await core.inventory.apply_stock_change(
                db, tenant_id=tenant_id, product_id=line.product_id, quantity_delta=float(line.quantity),
                movement_type="stock_in", user_id=user_id, reference_type="bakery_invoice", reference_id=row.id,
                notes=f"Void {row.invoice_number}",
            )
    await core._post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=row.invoice_number, source="bakery_invoice_void", source_id=row.id,
    )
    row.status = "void"
    row.void_reason = why
    row.voided_at = datetime.utcnow()
    row.void_restocked = bool(restock)
    await core._audit(db, tenant_id, user_id, "bakery_invoice_void", "bakery_invoice", row.id, {"reason": why, "restock": restock})
    await db.flush()
    return row


async def present_invoice(db: AsyncSession, row: m.BakeryInvoice, *, today: date, customer_name: str | None = None) -> dict:
    lines = (await db.execute(select(m.BakeryInvoiceLine).where(m.BakeryInvoiceLine.invoice_id == row.id))).scalars().all()
    left = _money(float(row.total or 0) - float(row.paid or 0))
    return {
        "id": row.id,
        "invoice_number": row.invoice_number,
        "customer_id": row.customer_id,
        "customer_name": customer_name,
        "invoice_date": row.invoice_date.isoformat(),
        "due_date": row.due_date.isoformat(),
        "status": row.status,
        "overdue": row.status in ("open", "part_paid") and row.due_date < today,
        "from_standing": bool(row.from_standing),
        "subtotal": _money(row.subtotal),
        "tax": _money(row.tax),
        "total": _money(row.total),
        "paid": _money(row.paid),
        "balance": left if row.status != "void" else 0.0,
        "notes": row.notes,
        "void_reason": row.void_reason,
        "items": [
            {"name": x.name, "quantity": _qty(x.quantity), "unit_price": _money(x.unit_price), "tax": _money(x.tax), "line_total": _money(x.line_total)}
            for x in lines
        ],
    }


async def list_invoices(db: AsyncSession, tenant_id: str, *, today: date, customer_id: str | None = None, limit: int = 100) -> list[dict]:
    stmt = (
        select(m.BakeryInvoice, m.BakeryCustomer.name)
        .join(m.BakeryCustomer, m.BakeryCustomer.id == m.BakeryInvoice.customer_id)
        .where(m.BakeryInvoice.tenant_id == tenant_id)
        .order_by(m.BakeryInvoice.invoice_date.desc(), m.BakeryInvoice.created_at.desc())
        .limit(limit)
    )
    if customer_id:
        stmt = stmt.where(m.BakeryInvoice.customer_id == customer_id)
    return [await present_invoice(db, row, today=today, customer_name=name) for row, name in (await db.execute(stmt)).all()]


async def run_standing(db: AsyncSession, tenant_id: str, *, day: date, user_id, role: str = "") -> dict:
    """Today's trade deliveries from standing orders: one invoice per customer, once a day."""
    weekday = day.weekday()
    rows = (
        await db.execute(
            select(m.BakeryStandingOrder, m.BakeryCustomer)
            .join(m.BakeryCustomer, m.BakeryCustomer.id == m.BakeryStandingOrder.customer_id)
            .where(
                m.BakeryStandingOrder.tenant_id == tenant_id,
                m.BakeryStandingOrder.is_active.is_(True),
                m.BakeryCustomer.is_active.is_(True),
            )
        )
    ).all()
    by_customer: dict[str, list] = {}
    names: dict[str, str] = {}
    for standing, customer in rows:
        if standing.days[weekday] == "1":
            by_customer.setdefault(customer.id, []).append(_Line(standing.product_id, float(standing.quantity), None))
            names[customer.id] = customer.name
    done, skipped = [], []
    for customer_id, lines in by_customer.items():
        already = (
            await db.execute(
                select(m.BakeryInvoice.id).where(
                    m.BakeryInvoice.tenant_id == tenant_id,
                    m.BakeryInvoice.customer_id == customer_id,
                    m.BakeryInvoice.invoice_date == day,
                    m.BakeryInvoice.from_standing.is_(True),
                    m.BakeryInvoice.status != "void",
                )
            )
        ).first()
        if already:
            skipped.append({"customer": names[customer_id], "reason": "Already made today"})
            continue
        try:
            async with db.begin_nested():
                inv = await create_invoice(
                    db, tenant_id, customer_id, lines, user_id=user_id, role=role, invoice_date=day, from_standing=True
                )
            done.append({"customer": names[customer_id], "invoice_number": inv.invoice_number, "total": _money(inv.total)})
        except HTTPException as exc:
            detail = exc.detail
            skipped.append({"customer": names[customer_id], "reason": detail.get("message") if isinstance(detail, dict) else str(detail)})
    return {"date": day.isoformat(), "made": done, "skipped": skipped}


async def due_today(db: AsyncSession, tenant_id: str, *, day: date) -> dict[str, float]:
    """What standing orders still need today, by product, for the bake list."""
    weekday = day.weekday()
    made = {
        cid
        for (cid,) in (
            await db.execute(
                select(m.BakeryInvoice.customer_id).where(
                    m.BakeryInvoice.tenant_id == tenant_id,
                    m.BakeryInvoice.invoice_date == day,
                    m.BakeryInvoice.from_standing.is_(True),
                    m.BakeryInvoice.status != "void",
                )
            )
        ).all()
    }
    need: dict[str, float] = {}
    rows = (
        await db.execute(
            select(m.BakeryStandingOrder)
            .join(m.BakeryCustomer, m.BakeryCustomer.id == m.BakeryStandingOrder.customer_id)
            .where(
                m.BakeryStandingOrder.tenant_id == tenant_id,
                m.BakeryStandingOrder.is_active.is_(True),
                m.BakeryCustomer.is_active.is_(True),
            )
        )
    ).scalars().all()
    for row in rows:
        if row.days[weekday] == "1" and row.customer_id not in made:
            need[row.product_id] = need.get(row.product_id, 0.0) + float(row.quantity)
    return need


# --- Customer payments -------------------------------------------------------------------


async def record_payment(db: AsyncSession, tenant_id: str, customer_id: str, payload, *, user_id) -> m.BakeryCustomerPayment:
    customer = await _customer(db, tenant_id, customer_id, lock=True)
    method = _pay_method(payload.method)
    amount = _money(payload.amount)
    owed = await balance(db, tenant_id, customer.id)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount paid")
    if amount > owed + 0.004:
        raise HTTPException(status_code=422, detail=f"{customer.name} owes {owed:.2f}. Take no more than that.")
    shift = await core._need_shift(db, tenant_id) if method == "cash" else None
    row = m.BakeryCustomerPayment(
        tenant_id=tenant_id,
        payment_number=await core._next_number(db, tenant_id, m.BakeryCustomerPayment, "TP"),
        customer_id=customer.id,
        shift_id=shift.id if shift else None,
        method=method,
        amount=amount,
        reference=optional_honest_narrative(getattr(payload, "reference", None), label="reference", max_length=100),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    left = amount
    open_rows = (
        await db.execute(
            select(m.BakeryInvoice)
            .where(
                m.BakeryInvoice.tenant_id == tenant_id,
                m.BakeryInvoice.customer_id == customer.id,
                m.BakeryInvoice.status.in_(("open", "part_paid")),
            )
            .order_by(m.BakeryInvoice.invoice_date.asc(), m.BakeryInvoice.created_at.asc())
            .with_for_update()
        )
    ).scalars().all()
    for inv in open_rows:
        if left <= 0.004:
            break
        due = _money(float(inv.total) - float(inv.paid or 0))
        take = min(due, left)
        inv.paid = _money(float(inv.paid or 0) + take)
        inv.status = "paid" if float(inv.paid) >= float(inv.total) - 0.004 else "part_paid"
        left = _money(left - take)
    description = f"Trade payment {row.payment_number} from {customer.name}"[:255]
    row.journal_entry_id = await core._post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": core._money_account(method), "debit": amount, "credit": 0, "description": description},
            {"account_code": "1100", "debit": 0, "credit": amount, "description": description},
        ],
        reference=row.payment_number, source="bakery_trade_payment", source_id=row.id,
    )
    if shift is not None:
        await core._pay(db, tenant_id, shift=shift, kind="trade_payment", method="cash", amount=amount, user_id=user_id)
    await core._audit(
        db, tenant_id, user_id, "bakery_trade_payment", "bakery_customer", customer.id,
        {"payment_number": row.payment_number, "amount": amount, "method": method},
    )
    await db.flush()
    return row


async def statement(db: AsyncSession, tenant_id: str, customer_id: str, *, start: date, end: date, today: date) -> dict:
    customer = await _customer(db, tenant_id, customer_id)
    begin, finish = await core._bounds(db, tenant_id, start, end)
    invoices = (
        await db.execute(
            select(m.BakeryInvoice).where(
                m.BakeryInvoice.tenant_id == tenant_id, m.BakeryInvoice.customer_id == customer.id, m.BakeryInvoice.status != "void"
            )
        )
    ).scalars().all()
    payments = (
        await db.execute(
            select(m.BakeryCustomerPayment).where(
                m.BakeryCustomerPayment.tenant_id == tenant_id, m.BakeryCustomerPayment.customer_id == customer.id
            )
        )
    ).scalars().all()
    local = await core._localiser(db, tenant_id)
    opening = sum(float(i.total) for i in invoices if i.invoice_date < start) - sum(
        float(p.amount) for p in payments if p.created_at < begin
    )
    rows = [
        (i.invoice_date, 0, {"date": i.invoice_date.isoformat(), "what": f"Invoice {i.invoice_number}", "debit": _money(i.total), "credit": 0.0})
        for i in invoices
        if start <= i.invoice_date <= end
    ] + [
        (local(p.created_at).date(), 1, {"date": local(p.created_at).date().isoformat(), "what": f"Payment {p.payment_number} ({p.method.replace('_', ' ')})", "debit": 0.0, "credit": _money(p.amount)})
        for p in payments
        if begin <= p.created_at < finish
    ]
    running = opening
    lines = []
    for _, _, line in sorted(rows, key=lambda r: (r[0], r[1])):
        running += line["debit"] - line["credit"]
        lines.append({**line, "balance": _money(running)})
    ages = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "over_60": 0.0}
    for inv in invoices:
        if inv.status not in ("open", "part_paid"):
            continue
        left = float(inv.total) - float(inv.paid or 0)
        late = (today - inv.due_date).days
        key = "current" if late <= 0 else "1_30" if late <= 30 else "31_60" if late <= 60 else "over_60"
        ages[key] += left
    return {
        "customer": await present_customer(db, tenant_id, customer, today=today),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "opening_balance": _money(opening),
        "lines": lines,
        "closing_balance": _money(running),
        "owed_by_age": {k: _money(v) for k, v in ages.items()},
    }


# --- Suppliers ---------------------------------------------------------------------------


async def supplier_by_name(db: AsyncSession, tenant_id: str, name: str) -> m.BakerySupplier:
    """The supplier with this name, added if new, so every credit purchase has someone to owe."""
    clean = require_honest_narrative(name, label="supplier", max_length=180)
    row = (
        await db.execute(
            select(m.BakerySupplier).where(m.BakerySupplier.tenant_id == tenant_id, func.lower(m.BakerySupplier.name) == clean.lower())
        )
    ).scalars().first()
    if row is None:
        row = m.BakerySupplier(tenant_id=tenant_id, name=clean)
        db.add(row)
        await db.flush()
    return row


async def _supplier(db: AsyncSession, tenant_id: str, supplier_id: str) -> m.BakerySupplier:
    row = await db.get(m.BakerySupplier, supplier_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return row


async def save_supplier(db: AsyncSession, tenant_id: str, payload, *, supplier_id: str | None = None) -> m.BakerySupplier:
    data = payload.model_dump(exclude_unset=True)
    if supplier_id:
        row = await _supplier(db, tenant_id, supplier_id)
        if "name" in data:
            row.name = require_honest_narrative(data["name"], label="supplier", max_length=180)
    else:
        row = await supplier_by_name(db, tenant_id, data.get("name") or "")
    if "phone" in data:
        row.phone = data["phone"]
    if "terms_days" in data and data["terms_days"] is not None:
        row.terms_days = data["terms_days"]
    if "notes" in data:
        row.notes = optional_honest_narrative(data["notes"], label="notes", max_length=500)
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    await db.flush()
    return row


async def supplier_owed(db: AsyncSession, tenant_id: str, supplier_id: str) -> float:
    bought = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakeryStockReceipt.total + m.BakeryStockReceipt.tax), 0)).where(
                m.BakeryStockReceipt.tenant_id == tenant_id,
                m.BakeryStockReceipt.supplier_id == supplier_id,
                m.BakeryStockReceipt.paid_with == "credit",
            )
        )
    ).scalar_one()
    paid = (
        await db.execute(
            select(func.coalesce(func.sum(m.BakerySupplierPayment.amount), 0)).where(
                m.BakerySupplierPayment.tenant_id == tenant_id, m.BakerySupplierPayment.supplier_id == supplier_id
            )
        )
    ).scalar_one()
    return _money(float(bought or 0) - float(paid or 0))


async def list_suppliers(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.BakerySupplier).where(m.BakerySupplier.tenant_id == tenant_id).order_by(m.BakerySupplier.name.asc()))
    ).scalars().all()
    out = []
    for row in rows:
        oldest = (
            await db.execute(
                select(func.min(m.BakeryStockReceipt.created_at)).where(
                    m.BakeryStockReceipt.supplier_id == row.id, m.BakeryStockReceipt.paid_with == "credit"
                )
            )
        ).scalar_one()
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "phone": row.phone,
                "terms_days": int(row.terms_days or 0),
                "notes": row.notes,
                "is_active": bool(row.is_active),
                "owed": await supplier_owed(db, tenant_id, row.id),
                "oldest_credit": oldest.isoformat() if oldest else None,
            }
        )
    return out


async def pay_supplier(db: AsyncSession, tenant_id: str, supplier_id: str, payload, *, user_id) -> m.BakerySupplierPayment:
    supplier = await _supplier(db, tenant_id, supplier_id)
    method = _pay_method(payload.method)
    amount = _money(payload.amount)
    owed = await supplier_owed(db, tenant_id, supplier.id)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount paid")
    if amount > owed + 0.004:
        raise HTTPException(status_code=422, detail=f"You owe {supplier.name} {owed:.2f}. Pay no more than that.")
    shift = None
    if method == "cash" and getattr(payload, "from_till", False):
        shift = await core._need_shift(db, tenant_id)
        in_drawer = _money(float(shift.opening_cash or 0) + await core.drawer_cash(db, tenant_id, shift))
        if amount > in_drawer + 0.004:
            raise HTTPException(status_code=409, detail=f"The drawer should only hold {in_drawer:.2f}")
    row = m.BakerySupplierPayment(
        tenant_id=tenant_id,
        payment_number=await core._next_number(db, tenant_id, m.BakerySupplierPayment, "SP"),
        supplier_id=supplier.id,
        shift_id=shift.id if shift else None,
        method=method,
        amount=amount,
        reference=optional_honest_narrative(getattr(payload, "reference", None), label="reference", max_length=100),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"Paid {supplier.name} {row.payment_number}"[:255]
    row.journal_entry_id = await core._post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": "2000", "debit": amount, "credit": 0, "description": description},
            {"account_code": core._money_account(method), "debit": 0, "credit": amount, "description": description},
        ],
        reference=row.payment_number, source="bakery_supplier_payment", source_id=row.id,
    )
    if shift is not None:
        await core._pay(db, tenant_id, shift=shift, kind="supplier_payment", method="cash", amount=-amount, user_id=user_id)
    await core._audit(
        db, tenant_id, user_id, "bakery_supplier_paid", "bakery_supplier", supplier.id,
        {"payment_number": row.payment_number, "amount": amount, "method": method},
    )
    await db.flush()
    return row


async def trade_numbers(db: AsyncSession, tenant_id: str, *, begin: datetime, finish: datetime, start: date, end: date) -> dict:
    """Trade invoices in a period, for the bakery report. An invoice counts on its own day; a
    void takes it back on the day of the void, like a refund."""
    rows = (
        await db.execute(
            select(m.BakeryInvoice).where(
                m.BakeryInvoice.tenant_id == tenant_id,
                m.BakeryInvoice.invoice_date >= start,
                m.BakeryInvoice.invoice_date <= end,
            )
        )
    ).scalars().all()
    voids = (
        await db.execute(
            select(m.BakeryInvoice).where(
                m.BakeryInvoice.tenant_id == tenant_id,
                m.BakeryInvoice.status == "void",
                m.BakeryInvoice.voided_at >= begin,
                m.BakeryInvoice.voided_at < finish,
            )
        )
    ).scalars().all()
    net = lambda r: float(r.total or 0) - float(r.tax or 0)  # noqa: E731
    return {
        "count": len(rows),
        "revenue": _money(sum(net(r) for r in rows) - sum(net(v) for v in voids)),
        "tax": _money(sum(float(r.tax or 0) for r in rows) - sum(float(v.tax or 0) for v in voids)),
        # Cost comes back only when the goods went back on the shelf.
        "cost": _money(
            sum(float(r.cost_of_goods or 0) for r in rows) - sum(float(v.cost_of_goods or 0) for v in voids if v.void_restocked)
        ),
    }
