"""FMCG van sales: load a van, sell from it, record losses and costs, and reconcile at close.

A van load sets stock aside for one open dispatch. Stock still leaves the books at the moment of
sale (delivery), damage or sample, exactly as for any delivery, so the accounts are always right.
Closing compares what should be left on the van with what the crew counted, and the cash that
should be handed in with what they hand in. A difference is never waved through: it needs a
manager and a written reason, and the stock difference is posted as a loss or gain.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import catalog as catalog_svc
from app import fmcg_orders as orders
from app import inventory
from app import models as m
from app.honesty import optional_honest_narrative, require_honest_narrative

EXPENSE_KINDS = frozenset({"fuel", "toll", "parking", "meal", "other"})
DAMAGE_KINDS = frozenset({"damaged", "sample"})
CLOSERS = frozenset({"company_admin", "fmcg_manager", "super_admin"})


async def _open_dispatch(db: AsyncSession, tenant_id: str, dispatch_id: str, *, lock: bool = False) -> m.FmcgDispatch:
    row = await orders._dispatch(db, tenant_id, dispatch_id, lock=lock)
    if row.status != "open":
        raise HTTPException(status_code=409, detail="This dispatch is closed")
    return row


async def _loads(db: AsyncSession, tenant_id: str, dispatch_id: str, *, lock: bool = False) -> list[m.FmcgVanLoad]:
    stmt = select(m.FmcgVanLoad).where(m.FmcgVanLoad.tenant_id == tenant_id, m.FmcgVanLoad.dispatch_id == dispatch_id)
    if lock:
        stmt = stmt.with_for_update()
    return list((await db.execute(stmt.order_by(m.FmcgVanLoad.id))).scalars().all())


def _left(row: m.FmcgVanLoad) -> float:
    return orders._qty(
        float(row.loaded_qty or 0) - float(row.sold_qty or 0) - float(row.damaged_qty or 0) - float(row.sample_qty or 0)
    )


async def _load_for(db, tenant_id: str, dispatch_id: str, product_id: str) -> m.FmcgVanLoad:
    row = (
        await db.execute(
            select(m.FmcgVanLoad)
            .where(
                m.FmcgVanLoad.tenant_id == tenant_id,
                m.FmcgVanLoad.dispatch_id == dispatch_id,
                m.FmcgVanLoad.product_id == product_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=409, detail="That product is not on this van")
    return row


# ---------------------------------------------------------------- load

async def load_van(db, *, tenant_id: str, dispatch_id: str, lines, user_id) -> dict:
    await _open_dispatch(db, tenant_id, dispatch_id, lock=True)
    seen: set[str] = set()
    for wanted in lines:
        if wanted.product_id in seen:
            raise HTTPException(status_code=422, detail="Each product can appear once per load")
        seen.add(wanted.product_id)
        product = (
            await db.execute(
                select(m.Product).where(m.Product.id == wanted.product_id, m.Product.tenant_id == tenant_id).with_for_update()
            )
        ).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        qty = orders._qty(wanted.quantity)
        free = orders._qty(float(product.stock_qty or 0) - await orders._on_trucks(db, tenant_id, product.id))
        if qty > free + 0.0005:
            raise HTTPException(
                status_code=409,
                detail={"code": "INSUFFICIENT_STOCK", "message": f"Only {free:g} {product.name} free to load"},
            )
        row = (
            await db.execute(
                select(m.FmcgVanLoad).where(
                    m.FmcgVanLoad.tenant_id == tenant_id,
                    m.FmcgVanLoad.dispatch_id == dispatch_id,
                    m.FmcgVanLoad.product_id == product.id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            db.add(m.FmcgVanLoad(tenant_id=tenant_id, dispatch_id=dispatch_id, product_id=product.id, loaded_qty=qty))
        else:
            row.loaded_qty = orders._qty(float(row.loaded_qty) + qty)
        await orders._audit(
            db, tenant_id, user_id, "fmcg_van_loaded", "fmcg_dispatch", dispatch_id,
            {"product_id": product.id, "quantity": qty},
        )
    await db.flush()
    return await summary(db, tenant_id=tenant_id, dispatch_id=dispatch_id)


# ---------------------------------------------------------------- sell

async def van_sale(
    db, *, tenant_id: str, dispatch_id: str, payload, payment_method: str | None, user_id, can_override: bool
) -> dict:
    """Book and deliver an order from the van in one step. Cash orders are paid on the spot."""
    await _open_dispatch(db, tenant_id, dispatch_id, lock=True)
    wanted: dict[str, float] = {}
    for line in payload.lines:
        wanted[line.product_id] = orders._qty(wanted.get(line.product_id, 0) + float(line.quantity))
    for product_id, qty in wanted.items():
        load = await _load_for(db, tenant_id, dispatch_id, product_id)
        if qty > _left(load) + 0.0005:
            product = await db.get(m.Product, product_id)
            raise HTTPException(
                status_code=409,
                detail={"code": "NOT_ON_VAN", "message": f"Only {_left(load):g} {product.name} left on the van"},
            )
    if payload.terms == "cash" and not payment_method:
        raise HTTPException(status_code=422, detail="Say how the outlet paid (cash, mobile money, card...)")
    order = await orders.create_order(db, tenant_id, payload, user_id=user_id, can_override=can_override)
    order.status = "loaded"
    order.dispatch_id = dispatch_id
    order = await orders.deliver_order(
        db, tenant_id, order.id, payment_method=payment_method, user_id=user_id, from_van=True
    )
    for product_id, qty in wanted.items():
        load = await _load_for(db, tenant_id, dispatch_id, product_id)
        load.sold_qty = orders._qty(float(load.sold_qty) + qty)
    await db.flush()
    return {"order": order, "summary": await summary(db, tenant_id=tenant_id, dispatch_id=dispatch_id)}


# ---------------------------------------------------------------- losses and costs

async def record_loss(db, *, tenant_id: str, dispatch_id: str, product_id: str, quantity: float, kind: str, note: str, user_id) -> dict:
    if kind not in DAMAGE_KINDS:
        raise HTTPException(status_code=422, detail="kind must be damaged or sample")
    text = require_honest_narrative(note, label="note", max_length=255)
    await _open_dispatch(db, tenant_id, dispatch_id)
    load = await _load_for(db, tenant_id, dispatch_id, product_id)
    qty = orders._qty(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be more than zero")
    if qty > _left(load) + 0.0005:
        raise HTTPException(status_code=409, detail=f"Only {_left(load):g} left on the van")
    product = await db.get(m.Product, product_id)
    cost = round(qty * float(product.cost_price or 0), 2)
    out = await catalog_svc.stock_out_with_batch(
        db, tenant_id=tenant_id, user_id=user_id, product_id=product_id, quantity=qty,
        reference_type="fmcg_van_loss", reference_id=dispatch_id, notes=f"Van {kind}: {text}",
    )
    from app import fmcg_warehouse as bins

    for taken in out.get("batches_consumed") or [{"batch_id": None, "quantity": qty}]:
        await bins.consume(db, tenant_id, product_id, taken["batch_id"], float(taken["quantity"]))
    if kind == "damaged":
        load.damaged_qty = orders._qty(float(load.damaged_qty) + qty)
    else:
        load.sample_qty = orders._qty(float(load.sample_qty) + qty)
    entry_id = None
    if cost > 0:
        entry_id = await orders._post(
            db, tenant_id, user_id=user_id, description=f"Van {kind} {product.name}",
            lines=[
                {"account_code": "6000", "debit": cost, "credit": 0, "description": f"Van {kind}"},
                {"account_code": "1200", "debit": 0, "credit": cost, "description": "Inventory out"},
            ],
            reference=dispatch_id[:8], source="fmcg_van_loss", source_id=dispatch_id,
        )
    await orders._audit(
        db, tenant_id, user_id, "fmcg_van_loss", "fmcg_dispatch", dispatch_id,
        {"product_id": product_id, "quantity": qty, "kind": kind, "cost": cost, "note": text},
    )
    await db.flush()
    return {"cost": orders._money(cost), "journal_entry_id": entry_id, **await summary(db, tenant_id=tenant_id, dispatch_id=dispatch_id)}


async def record_expense(db, *, tenant_id: str, dispatch_id: str, kind: str, amount: float, note: str | None, user_id) -> dict:
    if kind not in EXPENSE_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(sorted(EXPENSE_KINDS))}")
    text = optional_honest_narrative(note, label="note", max_length=255)
    await _open_dispatch(db, tenant_id, dispatch_id)
    paid = orders._money(amount)
    if paid <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount spent")
    row = m.FmcgVanExpense(
        tenant_id=tenant_id, dispatch_id=dispatch_id, kind=kind, amount=paid, note=text, created_by=user_id
    )
    db.add(row)
    await db.flush()
    row.journal_entry_id = await orders._post(
        db, tenant_id, user_id=user_id, description=f"Van {kind}",
        lines=[
            {"account_code": "6000", "debit": paid, "credit": 0, "description": f"Van {kind}"},
            {"account_code": orders._money_account("cash"), "debit": 0, "credit": paid, "description": "Paid from van takings"},
        ],
        reference=dispatch_id[:8], source="fmcg_van_expense", source_id=row.id,
    )
    dispatch = await orders._dispatch(db, tenant_id, dispatch_id)
    if dispatch.vehicle_id and kind in ("fuel", "toll", "parking"):
        db.add(
            m.FmcgVehicleLog(
                tenant_id=tenant_id, vehicle_id=dispatch.vehicle_id, kind="fuel" if kind == "fuel" else "other",
                log_date=date.today(), amount=paid, note=(text or kind)[:500], dispatch_id=dispatch_id,
                journal_entry_id=row.journal_entry_id, created_by=user_id,
            )
        )
    await orders._audit(
        db, tenant_id, user_id, "fmcg_van_expense", "fmcg_dispatch", dispatch_id, {"kind": kind, "amount": paid}
    )
    await db.flush()
    return await summary(db, tenant_id=tenant_id, dispatch_id=dispatch_id)


# ---------------------------------------------------------------- reconcile

async def summary(db, *, tenant_id: str, dispatch_id: str) -> dict:
    dispatch = await orders._dispatch(db, tenant_id, dispatch_id)
    loads = await _loads(db, tenant_id, dispatch_id)
    names = {}
    if loads:
        rows = (await db.execute(select(m.Product).where(m.Product.id.in_([l.product_id for l in loads])))).scalars().all()
        names = {p.id: p.name for p in rows}
    lines = [
        {
            "product_id": l.product_id,
            "product_name": names.get(l.product_id),
            "loaded": orders._qty(l.loaded_qty),
            "sold": orders._qty(l.sold_qty),
            "damaged": orders._qty(l.damaged_qty),
            "samples": orders._qty(l.sample_qty),
            "expected_back": _left(l),
            "counted": orders._qty(l.counted_qty) if l.counted_qty is not None else None,
            "variance": orders._qty(l.variance_qty) if l.variance_qty is not None else None,
        }
        for l in loads
    ]
    pay = dict(
        (
            await db.execute(
                select(m.FmcgPayment.method, func.coalesce(func.sum(m.FmcgPayment.amount), 0))
                .where(m.FmcgPayment.tenant_id == tenant_id, m.FmcgPayment.dispatch_id == dispatch_id)
                .group_by(m.FmcgPayment.method)
            )
        ).all()
    )
    credit = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgOrder.total), 0)).where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.dispatch_id == dispatch_id,
                m.FmcgOrder.status == "delivered",
                m.FmcgOrder.terms == "credit",
            )
        )
    ).scalar_one()
    spent = (
        await db.execute(
            select(m.FmcgVanExpense).where(
                m.FmcgVanExpense.tenant_id == tenant_id, m.FmcgVanExpense.dispatch_id == dispatch_id
            )
        )
    ).scalars().all()
    expected = await orders.expected_cash(db, tenant_id, dispatch_id)
    return {
        "dispatch_id": dispatch_id,
        "dispatch_number": dispatch.dispatch_number,
        "status": dispatch.status,
        "vehicle": dispatch.vehicle,
        "driver_name": dispatch.driver_name,
        "lines": lines,
        "money": {
            "cash_collected": orders._money(pay.get("cash", 0)),
            "mobile_money": orders._money(pay.get("mobile_money", 0)),
            "card": orders._money(pay.get("card", 0)),
            "bank_transfer": orders._money(pay.get("bank_transfer", 0)),
            "cheque": orders._money(pay.get("cheque", 0)),
            "credit_sales": orders._money(credit),
            "expenses": orders._money(sum(float(e.amount) for e in spent)),
            "cash_to_hand_in": expected,
        },
        "expenses": [{"id": e.id, "kind": e.kind, "amount": orders._money(e.amount), "note": e.note} for e in spent],
    }


async def close_van(
    db, *, tenant_id: str, dispatch_id: str, counted: dict[str, float], counted_cash: float, note: str | None,
    role: str, user_id,
) -> dict:
    dispatch = await _open_dispatch(db, tenant_id, dispatch_id, lock=True)
    loads = await _loads(db, tenant_id, dispatch_id, lock=True)
    missing = [l.product_id for l in loads if l.product_id not in counted]
    if missing:
        raise HTTPException(status_code=422, detail="Count every product that was loaded, even if it is zero")
    extra = [p for p in counted if p not in {l.product_id for l in loads}]
    if extra:
        raise HTTPException(status_code=422, detail="You counted a product that was never loaded on this van")
    stock_value = 0.0
    changes: list[tuple[m.FmcgVanLoad, float, m.Product]] = []
    for load in loads:
        qty = orders._qty(counted[load.product_id])
        if qty < 0:
            raise HTTPException(status_code=422, detail="Counts cannot be negative")
        diff = orders._qty(qty - _left(load))
        load.counted_qty = qty
        load.variance_qty = diff
        if abs(diff) > 0.0005:
            product = await db.get(m.Product, load.product_id)
            stock_value += diff * float(product.cost_price or 0)
            changes.append((load, diff, product))
    cash_diff = orders._money(counted_cash - await orders.expected_cash(db, tenant_id, dispatch_id))
    has_variance = bool(changes) or abs(cash_diff) > 0.004
    text = None
    if has_variance:
        if role not in CLOSERS:
            raise HTTPException(
                status_code=403,
                detail={"code": "VAN_VARIANCE_NEEDS_MANAGER", "message": "There is a difference. A manager must close this van."},
            )
        text = require_honest_narrative(note, label="reason for the difference", max_length=500)
    for load, diff, product in changes:
        if diff < 0:
            await catalog_svc.stock_out_with_batch(
                db, tenant_id=tenant_id, user_id=user_id, product_id=product.id, quantity=-diff,
                reference_type="fmcg_van_close", reference_id=dispatch_id, notes=f"Van count short: {text}",
            )
        else:
            await inventory.apply_stock_change(
                db, tenant_id=tenant_id, product_id=product.id, quantity_delta=diff, movement_type="stock_in",
                user_id=user_id, reference_type="fmcg_van_close", reference_id=dispatch_id, notes=f"Van count over: {text}",
            )
        value = round(abs(diff) * float(product.cost_price or 0), 2)
        if value > 0:
            short = diff < 0
            await orders._post(
                db, tenant_id, user_id=user_id, description=f"Van count {'short' if short else 'over'} {product.name}",
                lines=[
                    {"account_code": "6000" if short else "1200", "debit": value, "credit": 0, "description": "Van count"},
                    {"account_code": "1200" if short else "6000", "debit": 0, "credit": value, "description": "Van count"},
                ],
                reference=dispatch_id[:8], source="fmcg_van_close", source_id=load.id,
            )
    settled = await orders.settle_dispatch(db, tenant_id, dispatch_id, counted_cash=counted_cash, user_id=user_id)
    db.add(
        m.FmcgVanClosing(
            tenant_id=tenant_id, dispatch_id=dispatch_id, stock_variance_value=orders._money(stock_value),
            cash_variance=cash_diff, note=text, closed_by=user_id, closed_at=datetime.utcnow(),
        )
    )
    await orders._audit(
        db, tenant_id, user_id, "fmcg_van_closed", "fmcg_dispatch", dispatch_id,
        {"stock_variance_value": orders._money(stock_value), "cash_variance": cash_diff, "note": text},
    )
    await db.flush()
    return {**await summary(db, tenant_id=tenant_id, dispatch_id=dispatch_id), "settlement": settled,
            "stock_variance_value": orders._money(stock_value), "cash_variance": cash_diff}


async def performance(db, *, tenant_id: str) -> list[dict]:
    """One row per van trip: sales, losses, costs and variances, newest first."""
    rows = (
        await db.execute(
            select(m.FmcgDispatch)
            .join(m.FmcgVanLoad, m.FmcgVanLoad.dispatch_id == m.FmcgDispatch.id)
            .where(m.FmcgDispatch.tenant_id == tenant_id)
            .group_by(m.FmcgDispatch.id)
            .order_by(m.FmcgDispatch.dispatch_date.desc())
            .limit(60)
        )
    ).scalars().all()
    out = []
    for d in rows:
        s = await summary(db, tenant_id=tenant_id, dispatch_id=d.id)
        closing = (
            await db.execute(select(m.FmcgVanClosing).where(m.FmcgVanClosing.dispatch_id == d.id))
        ).scalar_one_or_none()
        sold = (
            await db.execute(
                select(func.coalesce(func.sum(m.FmcgOrder.total), 0)).where(
                    m.FmcgOrder.dispatch_id == d.id, m.FmcgOrder.status == "delivered", m.FmcgOrder.tenant_id == tenant_id
                )
            )
        ).scalar_one()
        out.append(
            {
                "dispatch_id": d.id, "dispatch_number": d.dispatch_number, "date": d.dispatch_date.isoformat(),
                "vehicle": d.vehicle, "driver_name": d.driver_name, "status": d.status,
                "sales": orders._money(sold), **s["money"],
                "stock_variance_value": orders._money(closing.stock_variance_value) if closing else None,
                "cash_variance": orders._money(closing.cash_variance) if closing else None,
            }
        )
    return out
