"""FMCG distributors: trade terms, statements, performance and who is falling behind.

A distributor is an ordinary outlet (so orders, credit limit, payment terms and the balance work as
they always did) with a profile on top: a kind, a price tier (a percentage off the list price, applied
before any promotion), a monthly sales target and an optional territory. Sales, returns, collections
and balances all come from the same delivered orders, payments and returns as the rest of FMCG.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import fmcg_orders as orders
from app import models as m
from app.honesty import money_json, optional_honest_narrative

KINDS = ("distributor", "wholesaler", "key_account", "supermarket")
# A distributor is flagged when any of these is true.
BEHIND_TARGET_PCT = 70.0
DECLINE_PCT = -20.0
LATE_SHARE_PCT = 30.0


def _m(v) -> float:
    return money_json(round(float(v or 0), 2))


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_distributor", entity_id=entity_id, details=details,
    )


async def _profile(db, tenant_id: str, distributor_id: str, *, lock: bool = False) -> m.FmcgDistributor:
    stmt = select(m.FmcgDistributor).where(m.FmcgDistributor.id == distributor_id, m.FmcgDistributor.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Distributor not found")
    return row


async def _territory_ok(db, tenant_id: str, territory_id: str | None) -> None:
    if territory_id and (await db.execute(select(m.FmcgTerritory.id).where(m.FmcgTerritory.id == territory_id, m.FmcgTerritory.tenant_id == tenant_id))).first() is None:
        raise HTTPException(status_code=404, detail="Territory not found")


async def create(db, *, tenant_id: str, user_id, customer_id: str, kind: str, price_discount_pct: float, monthly_target: float | None, territory_id: str | None, notes: str | None) -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(KINDS)}")
    outlet = await orders._outlet(db, tenant_id, customer_id)
    await _territory_ok(db, tenant_id, territory_id)
    if (await db.execute(select(m.FmcgDistributor.id).where(m.FmcgDistributor.tenant_id == tenant_id, m.FmcgDistributor.customer_id == outlet.id))).first():
        raise HTTPException(status_code=409, detail="That outlet already has a distributor profile")
    row = m.FmcgDistributor(
        tenant_id=tenant_id, customer_id=outlet.id, kind=kind, price_discount_pct=price_discount_pct, monthly_target=monthly_target,
        territory_id=territory_id, notes=optional_honest_narrative(notes, label="notes", max_length=500), created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_distributor_created", row.id, {"customer_id": outlet.id, "kind": kind, "discount": price_discount_pct})
    return await _present(db, row)


async def update(db, *, tenant_id: str, user_id, distributor_id: str, changes: dict) -> dict:
    row = await _profile(db, tenant_id, distributor_id, lock=True)
    if "kind" in changes:
        if changes["kind"] not in KINDS:
            raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(KINDS)}")
        row.kind = changes["kind"]
    if "territory_id" in changes:
        await _territory_ok(db, tenant_id, changes["territory_id"])
        row.territory_id = changes["territory_id"]
    for k in ("price_discount_pct", "monthly_target", "is_active"):
        if k in changes:
            setattr(row, k, changes[k])
    if "notes" in changes:
        row.notes = optional_honest_narrative(changes["notes"], label="notes", max_length=500)
    await _audit(db, tenant_id, user_id, "fmcg_distributor_updated", row.id, {k: str(v) for k, v in changes.items()})
    await db.flush()
    return await _present(db, row)


async def _month_sales(db, tenant_id: str, customer_id: str, start: date, end: date) -> float:
    rows = (await db.execute(select(m.FmcgOrder.total, m.FmcgOrder.tax).where(
        m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.customer_id == customer_id, m.FmcgOrder.status == "delivered",
        m.FmcgOrder.delivered_at >= datetime.combine(start, time.min), m.FmcgOrder.delivered_at <= datetime.combine(end, time.max)))).all()
    returned = (await db.execute(select(m.FmcgReturn.subtotal).where(
        m.FmcgReturn.tenant_id == tenant_id, m.FmcgReturn.customer_id == customer_id,
        m.FmcgReturn.created_at >= datetime.combine(start, time.min), m.FmcgReturn.created_at <= datetime.combine(end, time.max)))).scalars().all()
    return sum(float(t or 0) - float(x or 0) for t, x in rows) - sum(float(r or 0) for r in returned)


async def _present(db, row: m.FmcgDistributor) -> dict:
    outlet = await db.get(m.Party, row.customer_id)
    terr = await db.get(m.FmcgTerritory, row.territory_id) if row.territory_id else None
    today = date.today()
    mtd = await _month_sales(db, row.tenant_id, row.customer_id, today.replace(day=1), today)
    last = (await db.execute(select(m.FmcgOrder.delivered_at).where(
        m.FmcgOrder.tenant_id == row.tenant_id, m.FmcgOrder.customer_id == row.customer_id, m.FmcgOrder.status == "delivered").order_by(m.FmcgOrder.delivered_at.desc()).limit(1))).scalar_one_or_none()
    balance, limit = float(outlet.balance or 0), float(getattr(outlet, "credit_limit", 0) or 0)
    return {
        "id": row.id, "customer_id": row.customer_id, "name": outlet.name if outlet else None, "kind": row.kind,
        "price_discount_pct": money_json(row.price_discount_pct), "monthly_target": money_json(row.monthly_target) if row.monthly_target is not None else None,
        "territory_id": row.territory_id, "territory": terr.name if terr else None, "notes": row.notes, "is_active": row.is_active,
        "sales_this_month": _m(mtd), "target_pct": round(100 * mtd / float(row.monthly_target), 1) if row.monthly_target else None,
        "balance": _m(balance), "credit_limit": _m(limit), "over_limit": limit > 0 and balance > limit,
        "last_order": last.date().isoformat() if last else None,
    }


async def list_all(db, *, tenant_id: str) -> list[dict]:
    rows = (await db.execute(select(m.FmcgDistributor).where(m.FmcgDistributor.tenant_id == tenant_id))).scalars().all()
    out = [await _present(db, r) for r in rows]
    return sorted(out, key=lambda d: (d["name"] or ""))


async def statement(db, *, tenant_id: str, distributor_id: str, start: date, end: date) -> dict:
    row = await _profile(db, tenant_id, distributor_id)
    # Read the balance fresh: it is the anchor every line is worked back from.
    outlet = (await db.execute(select(m.Party).where(m.Party.id == row.customer_id, m.Party.tenant_id == tenant_id).execution_options(populate_existing=True))).scalar_one()
    begin, finish = datetime.combine(start, time.min), datetime.combine(end, time.max)

    async def events(after: datetime | None, before: datetime | None):
        ev = []
        stmt_o = select(m.FmcgOrder).where(m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.customer_id == row.customer_id, m.FmcgOrder.status == "delivered")
        stmt_p = select(m.FmcgPayment).where(m.FmcgPayment.tenant_id == tenant_id, m.FmcgPayment.customer_id == row.customer_id)
        stmt_r = select(m.FmcgReturn).where(m.FmcgReturn.tenant_id == tenant_id, m.FmcgReturn.customer_id == row.customer_id)
        def window(stmt, col):
            if after is not None:
                stmt = stmt.where(col >= after)
            if before is not None:
                stmt = stmt.where(col <= before)
            return stmt

        for o in (await db.execute(window(stmt_o, m.FmcgOrder.delivered_at))).scalars().all():
            ev.append((o.delivered_at, "Delivery", o.order_number, float(o.total or 0), 0.0))
        for p in (await db.execute(window(stmt_p, m.FmcgPayment.created_at))).scalars().all():
            ev.append((p.created_at, f"Payment ({p.method})", p.payment_number, 0.0, float(p.amount or 0)))
        for r in (await db.execute(window(stmt_r, m.FmcgReturn.created_at))).scalars().all():
            ev.append((r.created_at, "Return", r.return_number, 0.0, float(r.total or 0)))
        return sorted(ev, key=lambda e: e[0])

    after = await events(finish + timedelta(microseconds=1), None)
    inside = await events(begin, finish)
    closing = float(outlet.balance or 0) - sum(d for _, _, _, d, _ in after) + sum(c for _, _, _, _, c in after)
    opening = closing - sum(d for _, _, _, d, _ in inside) + sum(c for _, _, _, _, c in inside)
    run, lines = opening, []
    for when, kind, ref, debit, credit in inside:
        run += debit - credit
        lines.append({"date": when.date().isoformat(), "kind": kind, "reference": ref, "debit": _m(debit), "credit": _m(credit), "balance": _m(run)})
    return {
        "distributor": outlet.name if outlet else None, "period": {"start": start.isoformat(), "end": end.isoformat()},
        "opening_balance": _m(opening), "lines": lines, "closing_balance": _m(closing),
        "total_debits": _m(sum(l["debit"] for l in lines)), "total_credits": _m(sum(l["credit"] for l in lines)),
        "note": "Debits are delivered orders; credits are payments and returns. Balances are worked back from the outlet's current balance.",
    }


async def performance(db, *, tenant_id: str, distributor_id: str, start: date, end: date) -> dict:
    row = await _profile(db, tenant_id, distributor_id)
    outlet = await db.get(m.Party, row.customer_id)
    span = (end - start).days + 1
    prev_end, prev_start = start - timedelta(days=1), start - timedelta(days=span)
    begin, finish = datetime.combine(start, time.min), datetime.combine(end, time.max)
    ords = (await db.execute(select(m.FmcgOrder).where(
        m.FmcgOrder.tenant_id == tenant_id, m.FmcgOrder.customer_id == row.customer_id, m.FmcgOrder.status == "delivered",
        m.FmcgOrder.delivered_at >= begin, m.FmcgOrder.delivered_at <= finish))).scalars().all()
    rets = (await db.execute(select(m.FmcgReturn).where(
        m.FmcgReturn.tenant_id == tenant_id, m.FmcgReturn.customer_id == row.customer_id, m.FmcgReturn.created_at >= begin, m.FmcgReturn.created_at <= finish))).scalars().all()
    pays = (await db.execute(select(m.FmcgPayment.amount).where(
        m.FmcgPayment.tenant_id == tenant_id, m.FmcgPayment.customer_id == row.customer_id, m.FmcgPayment.created_at >= begin, m.FmcgPayment.created_at <= finish))).scalars().all()
    gross = sum(float(o.total or 0) - float(o.tax or 0) for o in ords)
    returned = sum(float(r.subtotal or 0) for r in rets)
    net = gross - returned
    cost = sum(float(o.cost_of_goods or 0) for o in ords) - sum(float(r.cost_of_goods or 0) for r in rets)
    prev = await _month_sales(db, tenant_id, row.customer_id, prev_start, prev_end)
    delivered_total = sum(float(o.total or 0) for o in ords)
    collected = sum(float(p or 0) for p in pays)
    aging = [r for r in (await orders.aging(db, tenant_id))["rows"] if r["customer_id"] == row.customer_id]
    owed = sum(r["total"] for r in aging)
    late = sum(r["total"] - r["current"] for r in aging)
    lines = (await db.execute(select(m.FmcgOrderLine.name, m.FmcgOrderLine.quantity, m.FmcgOrderLine.line_total, m.FmcgOrderLine.tax).where(
        m.FmcgOrderLine.tenant_id == tenant_id, m.FmcgOrderLine.order_id.in_([o.id for o in ords] or [""])))).all()
    prods: dict[str, list[float]] = {}
    for name, q, lt, tx in lines:
        g = prods.setdefault(name, [0.0, 0.0])
        g[0] += float(q or 0)
        g[1] += float(lt or 0) - float(tx or 0)
    target = float(row.monthly_target) * span / 30 if row.monthly_target else None
    growth = round(100 * (net - prev) / prev, 1) if prev > 0 else None
    attainment = round(100 * net / target, 1) if target else None
    late_share = round(100 * late / owed, 1) if owed > 0 else 0.0
    flags = []
    if attainment is not None and attainment < BEHIND_TARGET_PCT:
        flags.append("behind_target")
    if growth is not None and growth <= DECLINE_PCT:
        flags.append("sales_falling")
    if late_share >= LATE_SHARE_PCT and late > 0:
        flags.append("paying_late")
    if float(getattr(outlet, "credit_limit", 0) or 0) > 0 and float(outlet.balance or 0) > float(outlet.credit_limit):
        flags.append("over_credit_limit")
    if not ords:
        flags.append("no_orders")
    return {
        "distributor_id": row.id, "distributor": outlet.name if outlet else None, "period": {"start": start.isoformat(), "end": end.isoformat()},
        "orders": len(ords), "net_sales": _m(net), "returns": _m(returned), "return_rate_pct": round(100 * returned / gross, 1) if gross > 0 else 0.0,
        "gross_profit": _m(net - cost), "margin_pct": round(100 * (net - cost) / net, 1) if net > 0 else None,
        "previous_period_sales": _m(prev), "growth_pct": growth, "target": _m(target) if target is not None else None, "target_pct": attainment,
        "collected": _m(collected), "collection_rate_pct": round(100 * collected / delivered_total, 1) if delivered_total > 0 else None,
        "owed": _m(owed), "owed_late": _m(late), "late_share_pct": late_share, "flags": flags,
        "top_products": [{"product": k, "units": round(v[0], 3), "sales": _m(v[1])} for k, v in sorted(prods.items(), key=lambda t: -t[1][1])[:5]],
        "note": "Target is the monthly target scaled to the length of the period. Previous period is the same number of days just before.",
    }


async def ranking(db, *, tenant_id: str, start: date, end: date) -> list[dict]:
    """Every active distributor with its performance, the ones that need attention first."""
    rows = (await db.execute(select(m.FmcgDistributor).where(m.FmcgDistributor.tenant_id == tenant_id, m.FmcgDistributor.is_active.is_(True)))).scalars().all()
    out = [await performance(db, tenant_id=tenant_id, distributor_id=r.id, start=start, end=end) for r in rows]
    return sorted(out, key=lambda p: (-len(p["flags"]), p["net_sales"]))
