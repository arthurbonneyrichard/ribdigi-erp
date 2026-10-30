"""Restaurant period report: what sold, when, by whom, how it was paid, and what it cost.

Reads restaurant orders (the restaurant till's sales), recipe costs and waste. Shared stock
and accounting stay the engine; this only reports in restaurant words.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import restaurant as restaurant_svc
from app.honesty import money_json

MAX_DAYS = 366


def period_bounds(from_date: datetime | None, to_date: datetime | None) -> tuple[datetime, datetime]:
    """[start, end) by whole days. Default: the last 7 days including today."""
    today = restaurant_svc._now().replace(hour=0, minute=0, second=0, microsecond=0)
    last = (to_date or today).replace(hour=0, minute=0, second=0, microsecond=0)
    first = (from_date or (last - timedelta(days=6))).replace(hour=0, minute=0, second=0, microsecond=0)
    if first > last:
        raise HTTPException(status_code=422, detail="The start date must be on or before the end date.")
    if (last - first).days + 1 > MAX_DAYS:
        raise HTTPException(status_code=422, detail="Pick a period of one year or less.")
    return first, last + timedelta(days=1)


async def _orders(db: AsyncSession, tenant_id: str, scope, start: datetime, end: datetime, statuses: tuple[str, ...]):
    stmt = select(m.RestaurantOrder).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status.in_(statuses),
        m.RestaurantOrder.completed_at >= start,
        m.RestaurantOrder.completed_at < end,
    )
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


def _pct_change(now: float, before: float) -> float | None:
    if before <= 0:
        return None
    return money_json(round((now - before) / before * 100, 1))


async def period_report(
    db: AsyncSession,
    tenant_id: str,
    *,
    user_id: str | None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    await restaurant_svc._restaurant_tenant(db, tenant_id=tenant_id)
    start, end = period_bounds(from_date, to_date)
    days = (end - start).days
    scope = restaurant_svc._store_clause(
        m.RestaurantOrder.store_id, await restaurant_svc._allowed_stores(db, tenant_id, user_id)
    )

    orders = await _orders(db, tenant_id, scope, start, end, ("completed",))
    refunded = await _orders(db, tenant_id, scope, start, end, ("refunded",))
    prev = await _orders(db, tenant_id, scope, start - timedelta(days=days), start, ("completed",))

    sales = sum(float(o.total_amount or 0) for o in orders)
    before_tax = sum(float(o.subtotal or 0) for o in orders)
    prev_sales = sum(float(o.total_amount or 0) for o in prev)

    by_day: dict[str, dict] = {}
    for i in range(days):
        key = (start + timedelta(days=i)).date().isoformat()
        by_day[key] = {"date": key, "sales": 0.0, "orders": 0}
    by_hour = [{"hour": h, "sales": 0.0, "orders": 0} for h in range(24)]
    by_mode: dict[str, dict] = defaultdict(lambda: {"orders": 0, "sales": 0.0})
    by_method: dict[str, dict] = defaultdict(lambda: {"orders": 0, "sales": 0.0})
    by_staff: dict[str | None, dict] = defaultdict(lambda: {"orders": 0, "sales": 0.0})
    for o in orders:
        when = o.completed_at or o.created_at
        amount = float(o.total_amount or 0)
        day = by_day.get(when.date().isoformat())
        if day is not None:
            day["sales"] += amount
            day["orders"] += 1
        by_hour[when.hour]["sales"] += amount
        by_hour[when.hour]["orders"] += 1
        for bucket, key in ((by_mode, o.service_mode or "dine_in"), (by_method, o.payment_method or "cash"), (by_staff, o.created_by)):
            bucket[key]["orders"] += 1
            bucket[key]["sales"] += amount

    # Dishes: quantity and sales from order lines; cost from today's recipe (or the item's own cost).
    dishes: dict[str, dict] = {}
    if orders:
        lines = (
            await db.execute(
                select(m.RestaurantOrderLine, m.Product.name)
                .join(m.Product, m.Product.id == m.RestaurantOrderLine.product_id)
                .where(
                    m.RestaurantOrderLine.tenant_id == tenant_id,
                    m.RestaurantOrderLine.order_id.in_([o.id for o in orders]),
                )
            )
        ).all()
        for line, name in lines:
            row = dishes.setdefault(line.product_id, {"product_id": line.product_id, "name": name, "quantity": 0.0, "sales": 0.0})
            row["quantity"] += float(line.quantity or 0)
            row["sales"] += float(line.line_total or 0)
    food_cost = 0.0
    for row in dishes.values():
        unit_cost = float(await restaurant_svc.sale_line_cost(db, tenant_id, row["product_id"], 1) or 0)
        row["cost"] = unit_cost * row["quantity"]
        food_cost += row["cost"]
    dish_rows = sorted(dishes.values(), key=lambda r: (-r["sales"], r["name"]))
    for row in dish_rows:
        row["profit"] = money_json(round(row["sales"] - row["cost"], 2))
        row["food_cost_pct"] = money_json(round(row["cost"] / row["sales"] * 100, 1)) if row["sales"] > 0 else None
        row["quantity"] = money_json(round(row["quantity"], 3))
        row["sales"] = money_json(round(row["sales"], 2))
        row["cost"] = money_json(round(row["cost"], 2))

    # Waste booked in the period, valued at each ingredient's cost.
    waste_rows = (
        await db.execute(
            select(m.StockMovement, m.Product.name, m.Product.cost_price)
            .join(m.Product, m.Product.id == m.StockMovement.product_id)
            .where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.notes.contains(restaurant_svc.WASTE_PREFIX),
                m.StockMovement.created_at >= start,
                m.StockMovement.created_at < end,
            )
        )
    ).all()
    waste: dict[str, dict] = {}
    for move, name, cost in waste_rows:
        reason, _ = restaurant_svc.unpack_waste_notes(move.notes)
        if not reason:
            continue
        row = waste.setdefault(move.product_id, {"product_id": move.product_id, "name": name, "quantity": 0.0, "cost": 0.0})
        qty = abs(float(move.quantity or 0))
        row["quantity"] += qty
        row["cost"] += qty * float(cost or 0)
    waste_cost = sum(r["cost"] for r in waste.values())

    staff_ids = [sid for sid in by_staff if sid]
    names = {}
    if staff_ids:
        names = dict((await db.execute(select(m.User.id, m.User.full_name).where(m.User.id.in_(staff_ids)))).all())

    def _rows(bucket: dict, key_name: str) -> list[dict]:
        return sorted(
            (
                {key_name: key, "orders": v["orders"], "sales": money_json(round(v["sales"], 2))}
                for key, v in bucket.items()
            ),
            key=lambda r: -r["sales"],
        )

    staff_rows = _rows(by_staff, "user_id")
    for row in staff_rows:
        row["name"] = names.get(row["user_id"]) or ("Online orders" if row["user_id"] is None else "Former staff")

    count = len(orders)
    return {
        "from_date": start.date().isoformat(),
        "to_date": (end - timedelta(days=1)).date().isoformat(),
        "days": days,
        "totals": {
            "sales": money_json(round(sales, 2)),
            "before_tax": money_json(round(before_tax, 2)),
            "tax": money_json(round(sales - before_tax, 2)),
            "orders": count,
            "average_order": money_json(round(sales / count, 2)) if count else 0,
            "refunds": money_json(round(sum(float(o.total_amount or 0) for o in refunded), 2)),
            "refunded_orders": len(refunded),
            "food_cost": money_json(round(food_cost, 2)),
            "food_cost_pct": money_json(round(food_cost / before_tax * 100, 1)) if before_tax > 0 else None,
            "waste_cost": money_json(round(waste_cost, 2)),
            "previous_sales": money_json(round(prev_sales, 2)),
            "sales_change_pct": _pct_change(sales, prev_sales),
            "previous_orders": len(prev),
        },
        "by_day": [{**d, "sales": money_json(round(d["sales"], 2))} for d in by_day.values()],
        "by_hour": [{**h, "sales": money_json(round(h["sales"], 2))} for h in by_hour],
        "dishes": dish_rows,
        "by_service_mode": _rows(by_mode, "service_mode"),
        "by_payment_method": _rows(by_method, "payment_method"),
        "by_staff": staff_rows,
        "waste": sorted(
            (
                {**r, "quantity": money_json(round(r["quantity"], 3)), "cost": money_json(round(r["cost"], 2))}
                for r in waste.values()
            ),
            key=lambda r: -r["cost"],
        ),
    }


async def day_close(db: AsyncSession, tenant_id: str, *, user_id: str | None, day: datetime | None = None) -> dict:
    """One day on one sheet: takings, each till shift's cash count, refunds, cash spent, waste,
    and what is still open. Ready to close when every shift is counted and no bill is unpaid."""
    from sqlalchemy import or_

    from app import restaurant_till as till_svc

    day = day or restaurant_svc._now()
    period = await period_report(db, tenant_id, user_id=user_id, from_date=day, to_date=day)
    start = datetime.fromisoformat(period["from_date"])
    end = start + timedelta(days=1)
    scope = restaurant_svc._store_clause(
        m.RestaurantOrder.store_id, await restaurant_svc._allowed_stores(db, tenant_id, user_id)
    )

    shift_rows = list(
        (
            await db.execute(
                select(m.RestaurantTillShift)
                .where(
                    m.RestaurantTillShift.tenant_id == tenant_id,
                    m.RestaurantTillShift.opened_at < end,
                    or_(m.RestaurantTillShift.closed_at.is_(None), m.RestaurantTillShift.closed_at >= start),
                )
                .order_by(m.RestaurantTillShift.opened_at)
            )
        ).scalars()
    )
    shifts = [await till_svc.present_shift(db, s) for s in shift_rows]

    open_stmt = select(m.RestaurantOrder).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status.in_(tuple(restaurant_svc.OPEN_STATUSES)),
        m.RestaurantOrder.created_at < end,
    )
    if scope is not None:
        open_stmt = open_stmt.where(scope)
    open_orders = list((await db.execute(open_stmt)).scalars())

    cash_spent = list(
        (
            await db.execute(
                select(m.Expense).where(
                    m.Expense.tenant_id == tenant_id,
                    m.Expense.status == "approved",
                    m.Expense.payment_method == "cash",
                    m.Expense.expense_date >= start,
                    m.Expense.expense_date < end,
                )
            )
        ).scalars()
    )

    counted_short = sum(float(s["variance"]) for s in shifts if s.get("variance") is not None)
    open_shifts = [s for s in shifts if s["status"] != "closed"]
    return {
        "date": period["from_date"],
        "totals": period["totals"],
        "by_payment_method": period["by_payment_method"],
        "by_staff": period["by_staff"],
        "top_dishes": period["dishes"][:5],
        "waste": period["waste"],
        "shifts": shifts,
        "cash_variance": money_json(round(counted_short, 2)),
        "open_shifts": len(open_shifts),
        "open_orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "service_mode": o.service_mode,
                "total_amount": money_json(o.total_amount),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in sorted(open_orders, key=lambda o: o.created_at or start)
        ],
        "cash_expenses": [
            {
                "id": e.id,
                "payee": e.payee,
                "category": e.category,
                "description": e.description,
                "amount": money_json(e.amount),
            }
            for e in cash_spent
        ],
        "cash_expenses_total": money_json(round(sum(float(e.amount or 0) for e in cash_spent), 2)),
        "ready_to_close": not open_shifts and not open_orders,
    }
