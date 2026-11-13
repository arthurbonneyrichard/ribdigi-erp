"""FMCG desk selling: outlets, orders, van loading, delivery, collections and returns.

A distributor books an order for an outlet, loads it on a route's dispatch, delivers it, and
collects the money later. This lives on ``fmcg_*`` tables and never touches retail sales
documents or the till. Products and customers are the shared back-office masters.

Revenue is recognised at delivery, not at booking: stock leaves and the outlet owes the money
(debit 1100) on that day. A collection credits 1100 and pays the oldest delivered orders first.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import credit as credit_svc
from app import fmcg as fmcg_svc
from app import inventory
from app import models as m
from app import tax as tax_svc
from app import desk_dashboard as dash
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

METHODS = frozenset({"cash", "card", "mobile_money", "bank_transfer", "cheque"})
RETURN_REASONS = frozenset({"damaged", "expired", "unsold", "wrong_item", "other"})
ORDER_OPEN = ("booked", "loaded")
REF_ORDER = "fmcg_order"
REF_RETURN = "fmcg_return"

_JOBS = {
    "fmcg_rep": frozenset({"outlets", "orders", "collect", "visits"}),
    "fmcg_driver": frozenset({"deliver", "collect", "returns"}),
}
_WORDS = {
    "fmcg_rep": "Sales reps look after outlets, visits, orders and collections. Ask a manager for the rest.",
    "fmcg_driver": "Drivers deliver, collect and take returns. Ask a manager for the rest.",
}


def job(claims: dict, area: str) -> None:
    """Each FMCG role only does its own job. Managers and admins are not limited here."""
    role = str(claims.get("role") or "")
    if role in _JOBS and area not in _JOBS[role]:
        raise HTTPException(status_code=403, detail={"code": "FMCG_ROLE_JOB", "message": _WORDS[role]})


def _now() -> datetime:
    return datetime.utcnow()


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


def _qty(value) -> float:
    return money_json(round(float(value or 0), 3))


async def _next_number(db: AsyncSession, tenant_id: str, model, prefix: str) -> str:
    # key_share: see hotel._lock_numbers.
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    count = (await db.execute(select(func.count()).select_from(model).where(model.tenant_id == tenant_id))).scalar_one()
    return f"{prefix}-{int(count or 0) + 1:04d}"


async def _post(db, tenant_id: str, *, user_id, description: str, lines: list[dict], reference: str, source: str, source_id: str):
    await accounting.ensure_default_accounts(db, tenant_id)
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=reference,
        source_type=source,
        source_id=source_id,
    )
    return entry.id


async def _audit(db, tenant_id: str, user_id, action: str, entity: str, entity_id: str, details: dict) -> None:
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="fmcg",
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
    )


def _method(value: str | None) -> str:
    method = str(value or "").strip().lower()
    if method not in METHODS:
        raise HTTPException(status_code=422, detail="Choose how the outlet paid")
    return method


def _money_account(method: str) -> str:
    return accounting.pos_debit_account_for_payment_method(method)[0]


async def _outlet(db: AsyncSession, tenant_id: str, customer_id: str, *, lock: bool = False) -> m.Party:
    stmt = select(m.Party).where(m.Party.id == customer_id, m.Party.tenant_id == tenant_id, m.Party.kind == "customer")
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Outlet not found")
    return row


# --- Outlets -----------------------------------------------------------------------------


async def list_outlets(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.Party, m.FmcgCustomerAssignment, m.FmcgRoute)
            .outerjoin(
                m.FmcgCustomerAssignment,
                (m.FmcgCustomerAssignment.customer_id == m.Party.id)
                & (m.FmcgCustomerAssignment.tenant_id == tenant_id),
            )
            .outerjoin(m.FmcgRoute, m.FmcgRoute.id == m.FmcgCustomerAssignment.route_id)
            .where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer", m.Party.status == "active")
            .order_by(m.Party.name.asc())
        )
    ).all()
    return [
        {
            "id": party.id,
            "name": party.name,
            "phone": party.phone,
            "address": party.address,
            "credit_limit": _money(party.credit_limit),
            "payment_terms_days": int(party.payment_terms_days or 0),
            "balance": _money(party.balance),
            "route_id": route.id if route else None,
            "route_name": route.name if route else None,
            "salesperson_name": assignment.salesperson_name if assignment else None,
        }
        for party, assignment, route in rows
    ]


async def create_outlet(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.Party:
    row = m.Party(
        tenant_id=tenant_id,
        kind="customer",
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
        credit_limit=_money(payload.credit_limit),
        payment_terms_days=int(payload.payment_terms_days),
        profile_type="registered",
        status="active",
    )
    db.add(row)
    await db.flush()
    if payload.route_id:
        await fmcg_svc.upsert_customer_assignment(
            db,
            tenant_id=tenant_id,
            customer_id=row.id,
            route_id=payload.route_id,
            salesperson_name=payload.salesperson_name,
        )
    await _audit(db, tenant_id, user_id, "fmcg_outlet_created", "party", row.id, {"name": row.name})
    return row


# --- Orders ------------------------------------------------------------------------------


async def _priced_lines(db: AsyncSession, tenant_id: str, lines) -> tuple[list[dict], float, float, float, float]:
    """Price from the catalogue, never the request; the best running scheme comes off each line."""
    if not lines:
        raise HTTPException(status_code=422, detail="Add at least one product")
    out: list[dict] = []
    net_total = tax_total = gross_total = discount_total = 0.0
    for line in lines:
        product = await db.get(m.Product, line.product_id)
        if product is None or product.tenant_id != tenant_id or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")
        qty = _qty(line.quantity)
        price = _money(product.selling_price)
        if price <= 0:
            raise HTTPException(status_code=422, detail=f"{product.name} has no selling price")
        amount = _money(qty * price)
        discount, meta = await fmcg_svc.best_line_scheme_discount(
            db, tenant_id=tenant_id, product_id=product.id, line_qty=qty, line_amount=amount
        )
        discount = _money(min(float(discount or 0), amount))
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        net, tax, gross = tax_svc.compute_line_total(1, _money(amount - discount), spec.rate_pct, spec.pricing_mode)
        out.append(
            {
                "product": product,
                "quantity": qty,
                "unit_price": price,
                "discount": discount,
                "scheme_id": (meta or {}).get("scheme_id") if discount > 0 else None,
                "tax": _money(tax),
                "line_total": _money(gross),
            }
        )
        net_total += float(net)
        tax_total += float(tax)
        gross_total += float(gross)
        discount_total += discount
    return out, _money(net_total), _money(discount_total), _money(tax_total), _money(gross_total)


async def _committed_credit(db: AsyncSession, tenant_id: str, customer_id: str) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgOrder.total), 0)).where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.customer_id == customer_id,
                m.FmcgOrder.terms == "credit",
                m.FmcgOrder.status.in_(ORDER_OPEN),
            )
        )
    ).scalar_one()
    return _money(total)


async def create_order(
    db: AsyncSession, tenant_id: str, payload, *, user_id: str | None, can_override: bool
) -> m.FmcgOrder:
    outlet = await _outlet(db, tenant_id, payload.customer_id, lock=True)
    if outlet.status != "active":
        raise HTTPException(status_code=409, detail="This outlet is inactive")
    lines, net, discount, tax, gross = await _priced_lines(db, tenant_id, payload.lines)
    override = None
    if payload.terms == "credit":
        # Orders already booked count too, so a rep cannot slip past the limit one order at a time.
        override = credit_svc.enforce_customer_credit_limit(
            outlet,
            amount=_money(gross + await _committed_credit(db, tenant_id, outlet.id)),
            override=bool(payload.override_reason),
            override_allowed=can_override,
            override_reason=payload.override_reason,
        )
    assignment = (
        await db.execute(
            select(m.FmcgCustomerAssignment).where(
                m.FmcgCustomerAssignment.tenant_id == tenant_id, m.FmcgCustomerAssignment.customer_id == outlet.id
            )
        )
    ).scalars().first()
    row = m.FmcgOrder(
        tenant_id=tenant_id,
        order_number=await _next_number(db, tenant_id, m.FmcgOrder, "FO"),
        customer_id=outlet.id,
        route_id=assignment.route_id if assignment else None,
        rep_name=assignment.salesperson_name if assignment else None,
        terms=payload.terms,
        status="booked",
        subtotal=net,
        discount=discount,
        tax=tax,
        total=gross,
        notes=optional_honest_narrative(payload.notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    for line in lines:
        db.add(
            m.FmcgOrderLine(
                tenant_id=tenant_id,
                order_id=row.id,
                product_id=line["product"].id,
                name=line["product"].name,
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                discount=line["discount"],
                scheme_id=line["scheme_id"],
                tax=line["tax"],
                line_total=line["line_total"],
            )
        )
    await _audit(
        db, tenant_id, user_id, "fmcg_order_booked", "fmcg_order", row.id,
        {"order_number": row.order_number, "total": gross, "terms": row.terms, "credit_override": override},
    )
    await db.flush()
    return row


async def _order(db: AsyncSession, tenant_id: str, order_id: str, *, lock: bool = False) -> m.FmcgOrder:
    stmt = select(m.FmcgOrder).where(m.FmcgOrder.id == order_id, m.FmcgOrder.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return row


async def _lines(db: AsyncSession, order_id: str) -> list[m.FmcgOrderLine]:
    return list(
        (await db.execute(select(m.FmcgOrderLine).where(m.FmcgOrderLine.order_id == order_id))).scalars().all()
    )


async def _dispatch(db: AsyncSession, tenant_id: str, dispatch_id: str, *, lock: bool = False) -> m.FmcgDispatch:
    stmt = select(m.FmcgDispatch).where(m.FmcgDispatch.id == dispatch_id, m.FmcgDispatch.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    return row


async def _on_trucks(db: AsyncSession, tenant_id: str, product_id: str) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgOrderLine.quantity), 0))
            .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
            .where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.status == "loaded",
                m.FmcgOrderLine.product_id == product_id,
            )
        )
    ).scalar_one()
    return _qty(total)


async def load_order(db: AsyncSession, tenant_id: str, order_id: str, *, dispatch_id: str, user_id) -> m.FmcgOrder:
    """Put an order on a truck. Stock stays ours until delivery, but it cannot be promised twice."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status != "booked":
        raise HTTPException(status_code=409, detail=f"This order is {row.status}")
    dispatch = await _dispatch(db, tenant_id, dispatch_id)
    if dispatch.status != "open":
        raise HTTPException(status_code=409, detail="This dispatch is closed")
    for line in await _lines(db, row.id):
        product = await db.get(m.Product, line.product_id)
        free = _qty(float(product.stock_qty or 0) - await _on_trucks(db, tenant_id, line.product_id))
        if float(line.quantity) > free + 0.0005:
            raise HTTPException(
                status_code=409,
                detail={"code": "INSUFFICIENT_STOCK", "message": f"Only {free:g} {line.name} free to load"},
            )
    row.status = "loaded"
    row.dispatch_id = dispatch.id
    row.updated_at = _now()
    await db.flush()
    return row


async def _mark_stop(db, tenant_id: str, row: m.FmcgOrder, status: str, reason: str | None = None) -> None:
    if not row.route_id:
        return
    stop = (
        await db.execute(
            select(m.FmcgRouteStop).where(
                m.FmcgRouteStop.tenant_id == tenant_id,
                m.FmcgRouteStop.route_id == row.route_id,
                m.FmcgRouteStop.customer_id == row.customer_id,
                m.FmcgRouteStop.is_active.is_(True),
            )
        )
    ).scalars().first()
    if stop is not None:
        stop.delivery_status = status
        stop.delivered_at = _now() if status == "delivered" else None
        stop.fail_reason = reason


async def deliver_order(
    db: AsyncSession, tenant_id: str, order_id: str, *, payment_method: str | None, user_id: str | None
) -> m.FmcgOrder:
    """Goods handed over: stock leaves, revenue is booked and the outlet owes the money."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN:
        raise HTTPException(status_code=409, detail=f"This order is {row.status}")
    method = _method(payment_method) if row.terms == "cash" else None
    outlet = await _outlet(db, tenant_id, row.customer_id, lock=True)
    lines = await _lines(db, row.id)
    cost = 0.0
    for line in lines:
        product = await db.get(m.Product, line.product_id)
        if float(line.quantity) > float(product.stock_qty or 0) + 0.0005:
            raise HTTPException(
                status_code=409,
                detail={"code": "INSUFFICIENT_STOCK", "message": f"Only {_qty(product.stock_qty):g} {line.name} left"},
            )
        cost += float(line.quantity) * float(product.cost_price or 0)
        await inventory.apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=line.product_id,
            quantity_delta=-_qty(line.quantity),
            movement_type="stock_out",
            user_id=user_id,
            reference_type=REF_ORDER,
            reference_id=row.id,
            notes=f"FMCG delivery {row.order_number}",
        )
    gross, tax = _money(row.total), _money(row.tax)
    description = f"FMCG delivery {row.order_number}"
    journal = [
        {"account_code": "1100", "debit": gross, "credit": 0, "description": description},
        {"account_code": "4000", "debit": 0, "credit": _money(gross - tax), "description": description},
    ]
    if tax > 0:
        journal.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    accounting.append_cogs_lines(journal, _money(cost))
    row.cost_of_goods = _money(cost)
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=row.order_number, source=REF_ORDER, source_id=row.id,
    )
    row.status = "delivered"
    row.delivered_at = _now()
    row.due_date = date.today() + timedelta(days=int(outlet.payment_terms_days or 0) if row.terms == "credit" else 0)
    row.updated_at = _now()
    outlet.balance = _money(float(outlet.balance or 0) + gross)
    await _mark_stop(db, tenant_id, row, "delivered")
    await _audit(
        db, tenant_id, user_id, "fmcg_order_delivered", "fmcg_order", row.id,
        {"order_number": row.order_number, "total": gross},
    )
    await db.flush()
    if method:
        await collect(
            db, tenant_id, customer_id=outlet.id, amount=gross, method=method, order_id=row.id,
            dispatch_id=row.dispatch_id, notes=None, user_id=user_id,
        )
    return row


async def fail_delivery(db: AsyncSession, tenant_id: str, order_id: str, *, reason: str, user_id) -> m.FmcgOrder:
    """The outlet was shut or refused. Nothing moved, so the order goes back to be loaded again."""
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status != "loaded":
        raise HTTPException(status_code=409, detail="Only a loaded order can fail delivery")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    row.status = "booked"
    row.dispatch_id = None
    row.failed_reason = why
    row.updated_at = _now()
    await _mark_stop(db, tenant_id, row, "failed", why)
    await _audit(db, tenant_id, user_id, "fmcg_delivery_failed", "fmcg_order", row.id, {"reason": why})
    await db.flush()
    return row


async def cancel_order(db: AsyncSession, tenant_id: str, order_id: str, *, reason: str, user_id) -> m.FmcgOrder:
    row = await _order(db, tenant_id, order_id, lock=True)
    if row.status not in ORDER_OPEN:
        raise HTTPException(status_code=409, detail=f"This order is {row.status}. Use a return instead.")
    why = require_honest_narrative(reason, label="reason", max_length=255)
    row.status = "cancelled"
    row.cancel_reason = why
    row.dispatch_id = None
    row.updated_at = _now()
    await _audit(db, tenant_id, user_id, "fmcg_order_cancelled", "fmcg_order", row.id, {"reason": why})
    await db.flush()
    return row


def _due(row: m.FmcgOrder) -> float:
    return _money(float(row.total or 0) - float(row.paid or 0) - float(row.returned or 0))


async def present_order(db: AsyncSession, row: m.FmcgOrder) -> dict:
    party = await db.get(m.Party, row.customer_id)
    route = await db.get(m.FmcgRoute, row.route_id) if row.route_id else None
    return {
        "id": row.id,
        "order_number": row.order_number,
        "customer_id": row.customer_id,
        "customer_name": party.name if party else None,
        "route_id": row.route_id,
        "route_name": route.name if route else None,
        "dispatch_id": row.dispatch_id,
        "rep_name": row.rep_name,
        "terms": row.terms,
        "status": row.status,
        "subtotal": _money(row.subtotal),
        "discount": _money(row.discount),
        "tax": _money(row.tax),
        "total": _money(row.total),
        "paid": _money(row.paid),
        "returned": _money(row.returned),
        "balance_due": _due(row) if row.status == "delivered" else 0,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "failed_reason": row.failed_reason,
        "cancel_reason": row.cancel_reason,
        "notes": row.notes,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "name": line.name,
                "quantity": _qty(line.quantity),
                "returned_qty": _qty(line.returned_qty),
                "unit_price": _money(line.unit_price),
                "discount": _money(line.discount),
                "tax": _money(line.tax),
                "line_total": _money(line.line_total),
            }
            for line in await _lines(db, row.id)
        ],
    }


async def list_orders(db: AsyncSession, tenant_id: str, *, show: str = "open", limit: int = 200) -> list[m.FmcgOrder]:
    stmt = select(m.FmcgOrder).where(m.FmcgOrder.tenant_id == tenant_id)
    if show == "open":
        stmt = stmt.where(m.FmcgOrder.status.in_(ORDER_OPEN))
    elif show != "all":
        stmt = stmt.where(m.FmcgOrder.status == show)
    return list((await db.execute(stmt.order_by(m.FmcgOrder.created_at.desc()).limit(limit))).scalars().all())


# --- Collections -------------------------------------------------------------------------


async def collect(
    db: AsyncSession,
    tenant_id: str,
    *,
    customer_id: str,
    amount: float,
    method: str,
    order_id: str | None,
    dispatch_id: str | None,
    notes: str | None,
    user_id: str | None,
) -> m.FmcgPayment:
    """Take money from an outlet. It pays the chosen order, then the oldest ones."""
    how = _method(method)
    paid = _money(amount)
    if paid <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount received")
    outlet = await _outlet(db, tenant_id, customer_id, lock=True)
    if paid > _money(outlet.balance) + 0.005:
        raise HTTPException(status_code=409, detail=f"This outlet only owes {_money(outlet.balance):.2f}")
    if dispatch_id:
        dispatch = await _dispatch(db, tenant_id, dispatch_id)
        if dispatch.status != "open":
            raise HTTPException(status_code=409, detail="This dispatch is closed")
    number = await _next_number(db, tenant_id, m.FmcgPayment, "FR")
    row = m.FmcgPayment(
        tenant_id=tenant_id,
        payment_number=number,
        customer_id=outlet.id,
        order_id=order_id,
        dispatch_id=dispatch_id,
        method=how,
        amount=paid,
        notes=optional_honest_narrative(notes, label="notes", max_length=500),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    description = f"FMCG collection {number}"
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": _money_account(how), "debit": paid, "credit": 0, "description": description},
            {"account_code": "1100", "debit": 0, "credit": paid, "description": description},
        ],
        reference=number, source="fmcg_payment", source_id=row.id,
    )
    outlet.balance = _money(float(outlet.balance or 0) - paid)
    left = paid
    delivered = (
        await db.execute(
            select(m.FmcgOrder)
            .where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.customer_id == outlet.id,
                m.FmcgOrder.status == "delivered",
            )
            .order_by(m.FmcgOrder.delivered_at.asc())
            .with_for_update()
        )
    ).scalars().all()
    delivered.sort(key=lambda o: 0 if o.id == order_id else 1)
    for order in delivered:
        if left <= 0:
            break
        take = min(left, _due(order))
        if take > 0:
            order.paid = _money(float(order.paid or 0) + take)
            left = _money(left - take)
    await _audit(
        db, tenant_id, user_id, "fmcg_payment", "fmcg_payment", row.id,
        {"payment_number": number, "amount": paid, "method": how},
    )
    await db.flush()
    return row


async def present_payment(db: AsyncSession, row: m.FmcgPayment) -> dict:
    party = await db.get(m.Party, row.customer_id)
    return {
        "id": row.id,
        "payment_number": row.payment_number,
        "customer_id": row.customer_id,
        "customer_name": party.name if party else None,
        "order_id": row.order_id,
        "dispatch_id": row.dispatch_id,
        "method": row.method,
        "amount": _money(row.amount),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_payments(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[m.FmcgPayment]:
    return list(
        (
            await db.execute(
                select(m.FmcgPayment)
                .where(m.FmcgPayment.tenant_id == tenant_id)
                .order_by(m.FmcgPayment.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


# --- Returns -----------------------------------------------------------------------------


async def create_return(
    db: AsyncSession, tenant_id: str, order_id: str, *, lines, reason: str, resaleable: bool, user_id: str | None
) -> m.FmcgReturn:
    """Goods come back from a delivered order and the outlet is credited for them."""
    if reason not in RETURN_REASONS:
        raise HTTPException(status_code=422, detail="Choose a reason")
    order = await _order(db, tenant_id, order_id, lock=True)
    if order.status != "delivered":
        raise HTTPException(status_code=409, detail="Only a delivered order can have a return")
    outlet = await _outlet(db, tenant_id, order.customer_id, lock=True)
    by_id = {line.id: line for line in await _lines(db, order.id)}
    number = await _next_number(db, tenant_id, m.FmcgReturn, "FX")
    row = m.FmcgReturn(
        tenant_id=tenant_id,
        return_number=number,
        order_id=order.id,
        customer_id=outlet.id,
        reason=reason,
        resaleable=bool(resaleable),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    gross = tax = cost = 0.0
    for wanted in lines:
        line = by_id.get(wanted.line_id)
        if line is None:
            raise HTTPException(status_code=404, detail="That line is not on this order")
        qty = _qty(wanted.quantity)
        left = _qty(float(line.quantity) - float(line.returned_qty or 0))
        if qty > left + 0.0005:
            raise HTTPException(status_code=409, detail=f"Only {left:g} {line.name} can still come back")
        share = qty / float(line.quantity)
        line_gross, line_tax = _money(float(line.line_total) * share), _money(float(line.tax) * share)
        product = await db.get(m.Product, line.product_id)
        line.returned_qty = _qty(float(line.returned_qty or 0) + qty)
        gross += line_gross
        tax += line_tax
        db.add(
            m.FmcgReturnLine(
                tenant_id=tenant_id, return_id=row.id, order_line_id=line.id, product_id=line.product_id,
                name=line.name, quantity=qty, tax=line_tax, line_total=line_gross,
            )
        )
        if resaleable:
            cost += qty * float(product.cost_price or 0)
            await inventory.apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=line.product_id,
                quantity_delta=qty,
                movement_type="stock_in",
                user_id=user_id,
                reference_type=REF_RETURN,
                reference_id=row.id,
                notes=f"FMCG return {number}",
            )
    gross, tax, cost = _money(gross), _money(tax), _money(cost)
    if gross <= 0:
        raise HTTPException(status_code=422, detail="Enter what came back")
    description = f"FMCG return {number}"
    journal = [
        {"account_code": "4000", "debit": _money(gross - tax), "credit": 0, "description": description},
        {"account_code": "1100", "debit": 0, "credit": gross, "description": description},
    ]
    if tax > 0:
        journal.insert(1, {"account_code": "2100", "debit": tax, "credit": 0, "description": description})
    if cost > 0:
        accounting.append_cogs_lines(journal, cost, reverse=True)
    row.subtotal, row.tax, row.total, row.cost_of_goods = _money(gross - tax), tax, gross, cost
    row.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description, lines=journal,
        reference=number, source=REF_RETURN, source_id=row.id,
    )
    order.returned = _money(float(order.returned or 0) + gross)
    outlet.balance = _money(float(outlet.balance or 0) - gross)
    await _audit(
        db, tenant_id, user_id, "fmcg_return", "fmcg_return", row.id,
        {"return_number": number, "total": gross, "reason": reason, "resaleable": bool(resaleable)},
    )
    await db.flush()
    return row


async def present_return(db: AsyncSession, row: m.FmcgReturn) -> dict:
    party = await db.get(m.Party, row.customer_id)
    order = await db.get(m.FmcgOrder, row.order_id)
    return {
        "id": row.id,
        "return_number": row.return_number,
        "order_number": order.order_number if order else None,
        "customer_name": party.name if party else None,
        "reason": row.reason,
        "resaleable": bool(row.resaleable),
        "total": _money(row.total),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_returns(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[m.FmcgReturn]:
    return list(
        (
            await db.execute(
                select(m.FmcgReturn)
                .where(m.FmcgReturn.tenant_id == tenant_id)
                .order_by(m.FmcgReturn.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


# --- Settling a dispatch -----------------------------------------------------------------


async def unload(db: AsyncSession, tenant_id: str, dispatch_id: str) -> int:
    """Anything still on the truck when a dispatch ends goes back to be loaded again."""
    rows = (
        await db.execute(
            select(m.FmcgOrder).where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.dispatch_id == dispatch_id,
                m.FmcgOrder.status == "loaded",
            )
        )
    ).scalars().all()
    for row in rows:
        row.status = "booked"
        row.dispatch_id = None
        row.updated_at = _now()
    return len(rows)


async def expected_cash(db: AsyncSession, tenant_id: str, dispatch_id: str) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgPayment.amount), 0)).where(
                m.FmcgPayment.tenant_id == tenant_id,
                m.FmcgPayment.dispatch_id == dispatch_id,
                m.FmcgPayment.method == "cash",
            )
        )
    ).scalar_one()
    return _money(total)


async def settle_dispatch(
    db: AsyncSession, tenant_id: str, dispatch_id: str, *, counted_cash: float, user_id: str | None
) -> dict:
    """The driver hands in the cash. The difference is shown and recorded, not hidden."""
    row = await _dispatch(db, tenant_id, dispatch_id, lock=True)
    if row.status != "open":
        raise HTTPException(status_code=409, detail="This dispatch is already closed")
    expected = await expected_cash(db, tenant_id, row.id)
    counted = _money(counted_cash)
    returned = await unload(db, tenant_id, row.id)
    row.expected_cash = expected
    row.counted_cash = counted
    row.status = "closed"
    row.closed_at = _now()
    await _audit(
        db, tenant_id, user_id, "fmcg_dispatch_settled", "fmcg_dispatch", row.id,
        {"expected_cash": expected, "counted_cash": counted, "over_short": _money(counted - expected)},
    )
    await db.flush()
    return {
        "id": row.id,
        "status": row.status,
        "expected_cash": expected,
        "counted_cash": counted,
        "over_short": _money(counted - expected),
        "orders_back": returned,
    }


# --- Reports -----------------------------------------------------------------------------


async def period_numbers(db: AsyncSession, tenant_id: str, *, start: date, end: date) -> dict:
    begin, finish = datetime.combine(start, time.min), datetime.combine(end, time.max)
    orders = (
        await db.execute(
            select(m.FmcgOrder).where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.status == "delivered",
                m.FmcgOrder.delivered_at >= begin,
                m.FmcgOrder.delivered_at <= finish,
            )
        )
    ).scalars().all()
    returns = (
        await db.execute(
            select(m.FmcgReturn).where(
                m.FmcgReturn.tenant_id == tenant_id,
                m.FmcgReturn.created_at >= begin,
                m.FmcgReturn.created_at <= finish,
            )
        )
    ).scalars().all()
    payments = (
        await db.execute(
            select(m.FmcgPayment).where(
                m.FmcgPayment.tenant_id == tenant_id,
                m.FmcgPayment.created_at >= begin,
                m.FmcgPayment.created_at <= finish,
            )
        )
    ).scalars().all()
    revenue = sum(float(o.total or 0) - float(o.tax or 0) for o in orders)
    returned = sum(float(r.subtotal or 0) for r in returns)
    cost = sum(float(o.cost_of_goods or 0) for o in orders) - sum(float(r.cost_of_goods or 0) for r in returns)
    net = revenue - returned
    route_names = {
        r.id: r.name
        for r in (await db.execute(select(m.FmcgRoute).where(m.FmcgRoute.tenant_id == tenant_id))).scalars().all()
    }
    by_route: dict[str, float] = {}
    by_rep: dict[str, float] = {}
    for order in orders:
        route = route_names.get(order.route_id, "No route")
        by_route[route] = by_route.get(route, 0) + float(order.total or 0)
        rep = order.rep_name or "No rep"
        by_rep[rep] = by_rep.get(rep, 0) + float(order.total or 0)
    products: dict[str, dict] = {}
    if orders:
        lines = (
            await db.execute(select(m.FmcgOrderLine).where(m.FmcgOrderLine.order_id.in_([o.id for o in orders])))
        ).scalars().all()
        for line in lines:
            row = products.setdefault(line.name, {"name": line.name, "quantity": 0.0, "total": 0.0})
            row["quantity"] += float(line.quantity)
            row["total"] += float(line.line_total)
    by_method: dict[str, float] = {}
    for payment in payments:
        by_method[payment.method] = by_method.get(payment.method, 0) + float(payment.amount or 0)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "delivered_orders": len(orders),
        "revenue": _money(revenue),
        "returns": _money(returned),
        "net_sales": _money(net),
        "tax": _money(sum(float(o.tax or 0) for o in orders) - sum(float(r.tax or 0) for r in returns)),
        "scheme_discounts": _money(sum(float(o.discount or 0) for o in orders)),
        "cost_of_sales": _money(cost),
        "gross_profit": _money(net - cost),
        "gross_margin_percent": _money((net - cost) / net * 100) if net > 0 else 0,
        "collected": _money(sum(float(p.amount or 0) for p in payments)),
        "collected_by_method": {k: _money(v) for k, v in by_method.items()},
        "by_route": sorted(
            ({"name": k, "total": _money(v)} for k, v in by_route.items()), key=lambda r: -r["total"]
        ),
        "by_rep": sorted(({"name": k, "total": _money(v)} for k, v in by_rep.items()), key=lambda r: -r["total"]),
        "best_sellers": sorted(
            ({"name": p["name"], "quantity": _qty(p["quantity"]), "total": _money(p["total"])} for p in products.values()),
            key=lambda r: -r["total"],
        )[:15],
    }


async def aging(db: AsyncSession, tenant_id: str) -> dict:
    """Who owes what, split by how late it is."""
    today = date.today()
    orders = (
        await db.execute(
            select(m.FmcgOrder).where(m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "delivered")
        )
    ).scalars().all()
    rows: dict[str, dict] = {}
    for order in orders:
        due = _due(order)
        if due <= 0.004:
            continue
        late = (today - order.due_date).days if order.due_date else 0
        bucket = "current" if late <= 0 else "d1_30" if late <= 30 else "d31_60" if late <= 60 else "d61_plus"
        row = rows.setdefault(
            order.customer_id, {"customer_id": order.customer_id, "current": 0.0, "d1_30": 0.0, "d31_60": 0.0, "d61_plus": 0.0}
        )
        row[bucket] += due
    out = []
    for customer_id, row in rows.items():
        party = await db.get(m.Party, customer_id)
        total = sum(row[k] for k in ("current", "d1_30", "d31_60", "d61_plus"))
        out.append(
            {**{k: _money(v) if k != "customer_id" else v for k, v in row.items()},
             "name": party.name if party else "", "total": _money(total)}
        )
    out.sort(key=lambda r: -r["total"])
    return {"rows": out, "total": _money(sum(r["total"] for r in out))}


async def today(db: AsyncSession, tenant_id: str) -> dict:
    day = date.today()
    numbers = await period_numbers(db, tenant_id, start=day, end=day)
    open_count = (
        await db.execute(
            select(func.count()).select_from(m.FmcgOrder).where(
                m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "booked"
            )
        )
    ).scalar_one()
    loaded = (
        await db.execute(
            select(func.count()).select_from(m.FmcgOrder).where(
                m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.status == "loaded"
            )
        )
    ).scalar_one()
    owed = await aging(db, tenant_id)
    late = _money(sum(r["total"] - r["current"] for r in owed["rows"]))
    first, begin, finish = dash.window()
    rows = (
        await db.execute(
            select(m.FmcgOrder.delivered_at, m.FmcgOrder.total, m.FmcgOrder.tax).where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.status == "delivered",
                m.FmcgOrder.delivered_at >= begin,
                m.FmcgOrder.delivered_at <= finish,
            )
        )
    ).all()
    points: dict[date, float] = {}
    for when, total, tax in rows:
        points[when.date()] = points.get(when.date(), 0.0) + float(total or 0) - float(tax or 0)
    stale = (
        await db.execute(
            select(m.FmcgDispatch).where(
                m.FmcgDispatch.tenant_id == tenant_id,
                m.FmcgDispatch.status == "open",
                m.FmcgDispatch.dispatch_date < day,
            )
        )
    ).scalars().all()
    over = [o for o in await list_outlets(db, tenant_id) if o["credit_limit"] > 0 and o["balance"] > o["credit_limit"]]
    attention = []
    for dispatch in stale:
        attention.append(dash.item("warning", f"Dispatch {dispatch.dispatch_number} from {dispatch.dispatch_date.isoformat()} is not settled", "/fmcg?tab=orders"))
    if late > 0:
        attention.append(dash.item("warning", f"{_money(late):,.2f} owed past the due date", "/fmcg?tab=reports"))
    if over:
        attention.append(dash.item("warning", f"{dash.plural(len(over), 'outlet')} over the credit limit", "/fmcg?tab=outlets"))
    if open_count:
        attention.append(dash.item("info", f"{dash.plural(int(open_count), 'order')} waiting to be loaded", "/fmcg?tab=orders"))
    return {
        "date": day.isoformat(),
        "orders_to_load": int(open_count or 0),
        "orders_on_trucks": int(loaded or 0),
        "delivered_today": numbers["delivered_orders"],
        "sales_today": numbers["revenue"],
        "sales_yesterday": _money(points.get(day - timedelta(days=1), 0.0)),
        "collected_today": numbers["collected"],
        "owed_total": owed["total"],
        "owed_late": late,
        "trend": dash.trend("Delivered sales before tax, last 14 days", "money", dash.daily(points, first=first)),
        "attention": attention,
    }
