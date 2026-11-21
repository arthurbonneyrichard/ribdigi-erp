"""FMCG promotions: who may run one, who it is for, how much it may cost, and whether it paid.

A scheme prices a line at booking time (see ``fmcg.best_line_scheme_discount``). This module adds
the controls around it: a second person approves risky schemes, a scheme can be limited to
outlets, routes or territories, it can carry a money budget and a use limit, and a performance
report shows what it cost and what the promoted lines earned. Spend and uses are read from the
order lines themselves (cancelled orders do not count), so there is no second ledger to drift.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import fmcg as fmcg_svc
from app import models as m
from app.honesty import money_json, require_honest_narrative

POLICY_KEY = "fmcg_promo_policy"
DEFAULT_POLICY = {"approval_percent": 30.0, "approval_budget": 0.0}
TARGET_KINDS = ("customer", "route", "territory")


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_trade_scheme", entity_id=entity_id, details=details,
    )


# ---------------------------------------------------------------- policy

async def get_policy(db: AsyncSession, tenant_id: str) -> dict:
    tenant = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))).scalar_one()
    raw = (tenant.document_numbering or {}).get(POLICY_KEY) or {}
    out = dict(DEFAULT_POLICY)
    for key in out:
        try:
            value = float(raw.get(key, out[key]))
            if value >= 0:
                out[key] = value
        except (TypeError, ValueError):
            pass
    return out


async def set_policy(db: AsyncSession, tenant_id: str, *, approval_percent: float, approval_budget: float, user_id) -> dict:
    if not 0 <= approval_percent <= 100:
        raise HTTPException(status_code=422, detail="approval_percent must be between 0 and 100")
    if approval_budget < 0:
        raise HTTPException(status_code=422, detail="approval_budget cannot be negative")
    tenant = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())).scalar_one()
    data = dict(tenant.document_numbering or {})
    data[POLICY_KEY] = {"approval_percent": float(approval_percent), "approval_budget": float(approval_budget)}
    tenant.document_numbering = data
    await _audit(db, tenant_id, user_id, "fmcg_promo_policy_saved", tenant_id, data[POLICY_KEY])
    await db.flush()
    return await get_policy(db, tenant_id)


async def initial_status(db, tenant_id: str, *, scheme_type: str, value: float, budget: float | None) -> str:
    """A scheme needs a second person's approval when its discount or budget is above the company limits."""
    policy = await get_policy(db, tenant_id)
    if scheme_type == "percent" and value > policy["approval_percent"]:
        return "pending"
    if policy["approval_budget"] > 0 and budget is not None and budget > policy["approval_budget"]:
        return "pending"
    return "approved"


# ---------------------------------------------------------------- eligibility and usage

async def outlet_context(db, tenant_id: str, customer_id: str) -> dict:
    assignment = (
        await db.execute(
            select(m.FmcgCustomerAssignment).where(
                m.FmcgCustomerAssignment.tenant_id == tenant_id, m.FmcgCustomerAssignment.customer_id == customer_id
            )
        )
    ).scalars().first()
    route_id = assignment.route_id if assignment else None
    territory_id = None
    if route_id:
        territory_id = (
            await db.execute(
                select(m.FmcgTerritoryRoute.territory_id).where(
                    m.FmcgTerritoryRoute.tenant_id == tenant_id, m.FmcgTerritoryRoute.route_id == route_id
                )
            )
        ).scalar_one_or_none()
    return {"customer": customer_id, "route": route_id, "territory": territory_id}


async def outlet_eligible(db, tenant_id: str, scheme_id: str, ctx: dict | None) -> bool:
    targets = (
        await db.execute(
            select(m.FmcgSchemeTarget.kind, m.FmcgSchemeTarget.ref_id).where(
                m.FmcgSchemeTarget.tenant_id == tenant_id, m.FmcgSchemeTarget.scheme_id == scheme_id
            )
        )
    ).all()
    if not targets:
        return True
    if ctx is None:
        return False
    return any(ctx.get(kind) == ref for kind, ref in targets)


async def usage(db, tenant_id: str, scheme_id: str, *, lock: bool = False) -> tuple[float, int]:
    """Discount given and lines used so far, from live (not cancelled) FMCG orders."""
    if lock:
        await db.execute(
            select(m.FmcgTradeScheme.id).where(m.FmcgTradeScheme.id == scheme_id).with_for_update()
        )
    row = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgOrderLine.discount), 0), func.count(m.FmcgOrderLine.id))
            .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
            .where(
                m.FmcgOrderLine.tenant_id == tenant_id,
                m.FmcgOrderLine.scheme_id == scheme_id,
                m.FmcgOrder.status != "cancelled",
            )
        )
    ).one()
    return float(row[0] or 0), int(row[1] or 0)


# ---------------------------------------------------------------- list / create / decide

async def _targets(db, tenant_id: str, scheme_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.FmcgSchemeTarget).where(
                m.FmcgSchemeTarget.tenant_id == tenant_id, m.FmcgSchemeTarget.scheme_id == scheme_id
            )
        )
    ).scalars().all()
    out = []
    for t in rows:
        label = None
        if t.kind == "customer":
            label = getattr(await db.get(m.Party, t.ref_id), "name", None)
        elif t.kind == "route":
            label = getattr(await db.get(m.FmcgRoute, t.ref_id), "name", None)
        elif t.kind == "territory":
            label = getattr(await db.get(m.FmcgTerritory, t.ref_id), "name", None)
        out.append({"kind": t.kind, "ref_id": t.ref_id, "name": label})
    return out


async def _present(db, tenant_id: str, row: m.FmcgTradeScheme) -> dict:
    spent, uses = await usage(db, tenant_id, row.id)
    data = fmcg_svc.serialize_scheme(row)
    data.update(
        {
            "spent": money_json(round(spent, 2)),
            "uses": uses,
            "budget_left": money_json(round(float(row.budget) - spent, 2)) if row.budget is not None else None,
            "uses_left": int(row.max_uses) - uses if row.max_uses is not None else None,
            "targets": await _targets(db, tenant_id, row.id),
            "created_by": row.created_by,
            "approved_by": row.approved_by,
        }
    )
    return data


async def list_promotions(db, *, tenant_id: str, status: str | None = None) -> list[dict]:
    stmt = select(m.FmcgTradeScheme).where(m.FmcgTradeScheme.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(m.FmcgTradeScheme.status == status)
    rows = (await db.execute(stmt.order_by(m.FmcgTradeScheme.created_at.desc()))).scalars().all()
    return [await _present(db, tenant_id, r) for r in rows]


async def _check_target(db, tenant_id: str, kind: str, ref_id: str) -> None:
    if kind == "customer":
        found = await db.execute(
            select(m.Party.id).where(m.Party.id == ref_id, m.Party.tenant_id == tenant_id, m.Party.kind == "customer")
        )
    elif kind == "route":
        found = await db.execute(select(m.FmcgRoute.id).where(m.FmcgRoute.id == ref_id, m.FmcgRoute.tenant_id == tenant_id))
    elif kind == "territory":
        found = await db.execute(
            select(m.FmcgTerritory.id).where(m.FmcgTerritory.id == ref_id, m.FmcgTerritory.tenant_id == tenant_id)
        )
    else:
        raise HTTPException(status_code=422, detail=f"target kind must be one of: {', '.join(TARGET_KINDS)}")
    if found.first() is None:
        raise HTTPException(status_code=404, detail=f"That {kind} was not found")


async def create_promotion(
    db, *, tenant_id: str, user_id, code: str, name: str, scheme_type: str, value: float, buy_qty: int, get_qty: int,
    product_id, category_id, starts_on, ends_on, notes, budget: float | None, max_uses: int | None,
    min_qty: float | None, targets: list[tuple[str, str]],
) -> dict:
    if scheme_type == "percent" and not 0 < value <= 100:
        raise HTTPException(status_code=422, detail="A percent promotion is between 0 and 100")
    if scheme_type == "fixed" and value <= 0:
        raise HTTPException(status_code=422, detail="A fixed promotion needs an amount")
    if scheme_type == "bxgy" and (buy_qty < 1 or get_qty < 1):
        raise HTTPException(status_code=422, detail="Buy X get Y needs both quantities")
    if budget is not None and budget <= 0:
        raise HTTPException(status_code=422, detail="Budget must be more than zero")
    for kind, ref in targets:
        await _check_target(db, tenant_id, kind, ref)
    row = await fmcg_svc.create_scheme(
        db, tenant_id=tenant_id, code=code, name=name, scheme_type=scheme_type, value=value, buy_qty=buy_qty,
        get_qty=get_qty, product_id=product_id, category_id=category_id, starts_on=starts_on, ends_on=ends_on,
        notes=notes, created_by=user_id,
    )
    row.budget = budget
    row.max_uses = max_uses
    row.min_qty = min_qty
    row.status = await initial_status(db, tenant_id, scheme_type=scheme_type, value=value, budget=budget)
    for kind, ref in dict.fromkeys(targets):
        db.add(m.FmcgSchemeTarget(tenant_id=tenant_id, scheme_id=row.id, kind=kind, ref_id=ref))
    await _audit(
        db, tenant_id, user_id, "fmcg_promo_created", row.id,
        {"code": row.code, "status": row.status, "budget": budget, "max_uses": max_uses, "targets": len(targets)},
    )
    await db.flush()
    return await _present(db, tenant_id, row)


async def _locked(db, tenant_id: str, scheme_id: str) -> m.FmcgTradeScheme:
    row = (
        await db.execute(
            select(m.FmcgTradeScheme)
            .where(m.FmcgTradeScheme.id == scheme_id, m.FmcgTradeScheme.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    return row


async def approve(db, *, tenant_id: str, scheme_id: str, user_id) -> dict:
    row = await _locked(db, tenant_id, scheme_id)
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"This promotion is {row.status}")
    if row.created_by and row.created_by == user_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "SECOND_PERSON_NEEDED", "message": "Someone other than the person who made it must approve it"},
        )
    row.status = "approved"
    row.approved_by = user_id
    row.approved_at = datetime.utcnow()
    row.rejection_reason = None
    await _audit(db, tenant_id, user_id, "fmcg_promo_approved", row.id, {"code": row.code})
    await db.flush()
    return await _present(db, tenant_id, row)


async def reject(db, *, tenant_id: str, scheme_id: str, reason: str, user_id) -> dict:
    row = await _locked(db, tenant_id, scheme_id)
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"This promotion is {row.status}")
    row.status = "rejected"
    row.rejection_reason = require_honest_narrative(reason, label="reason", max_length=500)
    row.approved_by = user_id
    row.approved_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "fmcg_promo_rejected", row.id, {"code": row.code, "reason": row.rejection_reason})
    await db.flush()
    return await _present(db, tenant_id, row)


# ---------------------------------------------------------------- did it pay?

async def performance(db, *, tenant_id: str, scheme_id: str) -> dict:
    scheme = (
        await db.execute(
            select(m.FmcgTradeScheme).where(m.FmcgTradeScheme.id == scheme_id, m.FmcgTradeScheme.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if scheme is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    rows = (
        await db.execute(
            select(m.FmcgOrderLine, m.FmcgOrder, m.Product)
            .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgOrderLine.order_id)
            .join(m.Product, m.Product.id == m.FmcgOrderLine.product_id)
            .where(
                m.FmcgOrderLine.tenant_id == tenant_id,
                m.FmcgOrderLine.scheme_id == scheme_id,
                m.FmcgOrder.status != "cancelled",
            )
        )
    ).all()
    booked = {"lines": 0, "discount": 0.0}
    done = {"lines": 0, "units": 0.0, "discount": 0.0, "revenue": 0.0, "cost": 0.0}
    outlets: set[str] = set()
    for line, order, product in rows:
        booked["lines"] += 1
        booked["discount"] += float(line.discount or 0)
        if order.status != "delivered":
            continue
        outlets.add(order.customer_id)
        done["lines"] += 1
        done["units"] += float(line.quantity or 0)
        done["discount"] += float(line.discount or 0)
        done["revenue"] += float(line.line_total or 0) - float(line.tax or 0)
        done["cost"] += float(line.quantity or 0) * float(product.cost_price or 0)
    profit = done["revenue"] - done["cost"]
    spent, uses = await usage(db, tenant_id, scheme.id)
    return {
        "scheme": fmcg_svc.serialize_scheme(scheme),
        "committed": {"lines": booked["lines"], "discount": money_json(round(booked["discount"], 2))},
        "delivered": {
            "lines": done["lines"], "outlets": len(outlets), "units": money_json(round(done["units"], 3)),
            "discount_given": money_json(round(done["discount"], 2)),
            "revenue_after_discount": money_json(round(done["revenue"], 2)),
            "cost_of_goods": money_json(round(done["cost"], 2)),
            "gross_profit": money_json(round(profit, 2)),
            "margin_pct": round(100 * profit / done["revenue"], 1) if done["revenue"] > 0 else None,
            "discount_per_unit": money_json(round(done["discount"] / done["units"], 2)) if done["units"] > 0 else None,
        },
        "budget": money_json(scheme.budget) if scheme.budget is not None else None,
        "budget_used_pct": round(100 * spent / float(scheme.budget), 1) if scheme.budget else None,
        "uses": uses,
        "note": "Cost of goods uses each product's current cost price.",
    }
