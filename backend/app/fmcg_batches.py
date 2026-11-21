"""FMCG batches: expiry watch, quarantine, write-off and product recalls.

Delivery already takes stock first-expiry-first-out and records which batches each order line
used (``fmcg_line_batches``). That record is what lets a recall name every outlet that received a
bad batch. Holds reuse the shared ``batch_holds`` table, so a held batch is refused by every
stock-out path, not only FMCG.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import inventory
from app import models as m
from app import pharmacy as pharmacy_svc
from app.honesty import money_json, require_honest_narrative

POLICY_KEY = "fmcg_batch_policy"
DEFAULT_WARN_DAYS = [90, 60, 30, 14, 7]
WRITE_OFF_REASONS = {"expiry": "expiry", "damage": "damage", "recall": "damage", "other": "lost"}
STATUSES = ("all", "ok", "near", "expired", "held")


def _qty(value) -> float:
    return money_json(round(float(value or 0), 3))


async def _audit(db, tenant_id, user_id, action, entity, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity=entity, entity_id=entity_id, details=details,
    )


async def _tenant(db: AsyncSession, tenant_id: str, *, lock: bool = False) -> m.Tenant:
    stmt = select(m.Tenant).where(m.Tenant.id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one()


# ---------------------------------------------------------------- policy

def clean_warn_days(days) -> list[int]:
    if not isinstance(days, list) or not 1 <= len(days) <= 6:
        raise HTTPException(status_code=422, detail="Give between 1 and 6 warning periods, in days")
    out = set()
    for d in days:
        if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 365:
            raise HTTPException(status_code=422, detail="Each warning period is a whole number of days, 1 to 365")
        out.add(d)
    return sorted(out, reverse=True)


async def get_policy(db: AsyncSession, tenant_id: str) -> dict:
    raw = ((await _tenant(db, tenant_id)).document_numbering or {}).get(POLICY_KEY) or {}
    days = raw.get("warn_days")
    try:
        days = clean_warn_days(days) if days else list(DEFAULT_WARN_DAYS)
    except HTTPException:
        days = list(DEFAULT_WARN_DAYS)
    return {"warn_days": days}


async def set_policy(db: AsyncSession, tenant_id: str, *, warn_days: list[int], user_id) -> dict:
    tenant = await _tenant(db, tenant_id, lock=True)
    data = dict(tenant.document_numbering or {})
    data[POLICY_KEY] = {"warn_days": clean_warn_days(warn_days)}
    tenant.document_numbering = data
    await _audit(db, tenant_id, user_id, "fmcg_batch_policy_saved", "tenant", tenant_id, data[POLICY_KEY])
    await db.flush()
    return await get_policy(db, tenant_id)


# ---------------------------------------------------------------- batch list

def _state(batch: m.ProductBatch, held: set[str], widest: int, today: date) -> tuple[str, int | None]:
    exp = batch.expiry_date.date() if batch.expiry_date else None
    days = (exp - today).days if exp else None
    if batch.id in held:
        return "held", days
    if days is not None and days < 0:
        return "expired", days
    if days is not None and days <= widest:
        return "near", days
    return "ok", days


async def list_batches(
    db: AsyncSession, *, tenant_id: str, status: str = "all", q: str | None = None, include_empty: bool = False
) -> dict:
    if status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(STATUSES)}")
    policy = await get_policy(db, tenant_id)
    widest = max(policy["warn_days"])
    stmt = (
        select(m.ProductBatch, m.Product)
        .join(m.Product, m.Product.id == m.ProductBatch.product_id)
        .where(m.ProductBatch.tenant_id == tenant_id)
    )
    if not include_empty:
        stmt = stmt.where(m.ProductBatch.quantity > 0)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(m.Product.name).like(like) | func.lower(m.ProductBatch.batch_number).like(like))
    rows = (await db.execute(stmt.order_by(m.ProductBatch.expiry_date.asc().nulls_last()))).all()
    held = await pharmacy_svc.open_hold_batch_ids(db, tenant_id, [b.id for b, _ in rows])
    today = date.today()
    out, totals = [], {"ok": 0, "near": 0, "expired": 0, "held": 0}
    for batch, product in rows:
        state, days = _state(batch, held, widest, today)
        value = _qty(batch.quantity) * float(product.cost_price or 0)
        totals[state] += 1
        if status != "all" and state != status:
            continue
        band = next((d for d in sorted(policy["warn_days"]) if days is not None and 0 <= days <= d), None)
        out.append(
            {
                "id": batch.id,
                "product_id": product.id,
                "product_name": product.name,
                "batch_number": batch.batch_number,
                "quantity": _qty(batch.quantity),
                "manufacturing_date": batch.manufacturing_date.date().isoformat() if batch.manufacturing_date else None,
                "expiry_date": batch.expiry_date.date().isoformat() if batch.expiry_date else None,
                "days_to_expiry": days,
                "warning_band_days": band,
                "state": state,
                "value_at_cost": money_json(round(value, 2)),
            }
        )
    return {"policy": policy, "counts": totals, "batches": out}


async def _batch(db, tenant_id: str, batch_id: str, *, lock: bool = False) -> m.ProductBatch:
    stmt = select(m.ProductBatch).where(m.ProductBatch.id == batch_id, m.ProductBatch.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return row


# ---------------------------------------------------------------- hold / release

async def hold_batch(db, *, tenant_id: str, batch_id: str, reason: str, user_id) -> dict:
    row = await pharmacy_svc.create_hold(
        db, tenant_id=tenant_id, created_by=user_id, batch_id=batch_id, hold_type="quarantine", reason=reason
    )
    await _audit(db, tenant_id, user_id, "fmcg_batch_quarantined", "product_batch", batch_id, {"reason": row.reason})
    return {"hold_id": row.id, "batch_id": batch_id, "status": row.status}


async def release_batch(db, *, tenant_id: str, batch_id: str, user_id) -> dict:
    hold = (
        await db.execute(
            select(m.BatchHold).where(
                m.BatchHold.tenant_id == tenant_id, m.BatchHold.batch_id == batch_id, m.BatchHold.status == "open"
            )
        )
    ).scalar_one_or_none()
    if hold is None:
        raise HTTPException(status_code=404, detail="That batch is not on hold")
    if hold.hold_type == "recall":
        open_recall = (
            await db.execute(
                select(m.FmcgRecallBatch.id)
                .join(m.FmcgRecall, m.FmcgRecall.id == m.FmcgRecallBatch.recall_id)
                .where(
                    m.FmcgRecallBatch.tenant_id == tenant_id,
                    m.FmcgRecallBatch.batch_id == batch_id,
                    m.FmcgRecall.status == "open",
                )
            )
        ).first()
        if open_recall:
            raise HTTPException(
                status_code=409,
                detail={"code": "BATCH_IN_OPEN_RECALL", "message": "Close the recall before releasing this batch"},
            )
    await pharmacy_svc.release_hold(db, tenant_id=tenant_id, hold_id=hold.id)
    await _audit(db, tenant_id, user_id, "fmcg_batch_released", "product_batch", batch_id, {})
    return {"batch_id": batch_id, "status": "released"}


# ---------------------------------------------------------------- write-off

async def write_off(
    db, *, tenant_id: str, batch_id: str, quantity: float, reason_code: str, reason: str, user_id
) -> dict:
    """Take bad stock out of the books: stock out, then debit losses and credit inventory at cost."""
    if reason_code not in WRITE_OFF_REASONS:
        raise HTTPException(status_code=422, detail=f"reason_code must be one of: {', '.join(WRITE_OFF_REASONS)}")
    text = require_honest_narrative(reason, label="write-off reason", max_length=500)
    batch = await _batch(db, tenant_id, batch_id, lock=True)
    qty = _qty(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be more than zero")
    if qty > _qty(batch.quantity) + 0.0005:
        raise HTTPException(status_code=409, detail=f"Only {_qty(batch.quantity):g} left in this batch")
    held = await pharmacy_svc.open_hold_batch_ids(db, tenant_id, [batch.id])
    expired = bool(batch.expiry_date and batch.expiry_date.date() < date.today())
    if reason_code == "expiry" and not expired:
        raise HTTPException(status_code=409, detail="This batch has not expired. Pick another reason")
    if reason_code != "expiry" and not expired and batch.id not in held:
        raise HTTPException(
            status_code=409,
            detail={"code": "QUARANTINE_FIRST", "message": "Put the batch on hold before writing off good-dated stock"},
        )
    product = await db.get(m.Product, batch.product_id)
    cost = round(qty * float(product.cost_price or 0), 2)
    batch.quantity = _qty(float(batch.quantity) - qty)
    batch.updated_at = datetime.utcnow()
    await inventory.apply_stock_change(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=-qty,
        movement_type="stock_out",
        user_id=user_id,
        reference_type="fmcg_write_off",
        reference_id=batch.id,
        notes=text,
        reason=WRITE_OFF_REASONS[reason_code],
        batch_id=batch.id,
    )
    from app import fmcg_warehouse as bins

    await bins.consume(db, tenant_id, product.id, batch.id, qty)
    entry_id = None
    if cost > 0:
        await accounting.ensure_default_accounts(db, tenant_id)
        entry = await accounting.post_journal_entry(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            description=f"Stock write-off {product.name} {batch.batch_number}",
            lines=[
                {"account_code": "6000", "debit": cost, "credit": 0, "description": "Stock loss"},
                {"account_code": "1200", "debit": 0, "credit": cost, "description": "Inventory out"},
            ],
            reference=batch.batch_number,
            source_type="fmcg_write_off",
            source_id=batch.id,
        )
        entry_id = entry.id
    await _audit(
        db, tenant_id, user_id, "fmcg_batch_written_off", "product_batch", batch.id,
        {"quantity": qty, "cost": cost, "reason_code": reason_code, "reason": text},
    )
    await db.flush()
    return {"batch_id": batch.id, "written_off": qty, "cost": money_json(cost), "journal_entry_id": entry_id}


# ---------------------------------------------------------------- recalls

async def _next_recall_number(db, tenant_id: str) -> str:
    await db.execute(select(m.Tenant.id).where(m.Tenant.id == tenant_id).with_for_update(key_share=True))
    count = (
        await db.execute(select(func.count()).select_from(m.FmcgRecall).where(m.FmcgRecall.tenant_id == tenant_id))
    ).scalar_one()
    return f"RC-{int(count or 0) + 1:04d}"


async def _delivered(db, tenant_id: str, batch_id: str) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(m.FmcgLineBatch.quantity - m.FmcgLineBatch.returned_qty), 0)).where(
                m.FmcgLineBatch.tenant_id == tenant_id, m.FmcgLineBatch.batch_id == batch_id
            )
        )
    ).scalar_one()
    return _qty(total)


async def create_recall(db, *, tenant_id: str, title: str, reason: str, batch_ids: list[str], user_id) -> dict:
    title = require_honest_narrative(title, label="recall title", max_length=200)
    reason = require_honest_narrative(reason, label="recall reason", max_length=1000)
    ids = list(dict.fromkeys(batch_ids))
    if not ids:
        raise HTTPException(status_code=422, detail="Pick at least one batch")
    batches = [await _batch(db, tenant_id, b) for b in ids]
    row = m.FmcgRecall(
        tenant_id=tenant_id,
        recall_number=await _next_recall_number(db, tenant_id),
        title=title,
        reason=reason,
        status="open",
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    for batch in batches:
        await pharmacy_svc.create_hold(
            db, tenant_id=tenant_id, created_by=user_id, batch_id=batch.id, hold_type="recall", reason=reason
        )
        db.add(
            m.FmcgRecallBatch(
                tenant_id=tenant_id,
                recall_id=row.id,
                batch_id=batch.id,
                quantity_in_stock=_qty(batch.quantity),
                quantity_delivered=await _delivered(db, tenant_id, batch.id),
            )
        )
    await _audit(db, tenant_id, user_id, "fmcg_recall_opened", "fmcg_recall", row.id, {"batches": ids, "title": title})
    await db.flush()
    return await recall_detail(db, tenant_id=tenant_id, recall_id=row.id)


async def _get_recall(db, tenant_id: str, recall_id: str, *, lock: bool = False) -> m.FmcgRecall:
    stmt = select(m.FmcgRecall).where(m.FmcgRecall.id == recall_id, m.FmcgRecall.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Recall not found")
    return row


def _recall_row(r: m.FmcgRecall) -> dict:
    return {
        "id": r.id,
        "recall_number": r.recall_number,
        "title": r.title,
        "reason": r.reason,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "closed_at": r.closed_at.isoformat() if r.closed_at else None,
    }


async def list_recalls(db, *, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.FmcgRecall).where(m.FmcgRecall.tenant_id == tenant_id).order_by(m.FmcgRecall.created_at.desc())
        )
    ).scalars().all()
    return [_recall_row(r) for r in rows]


async def recall_detail(db, *, tenant_id: str, recall_id: str) -> dict:
    recall = await _get_recall(db, tenant_id, recall_id)
    links = (
        await db.execute(
            select(m.FmcgRecallBatch, m.ProductBatch, m.Product)
            .join(m.ProductBatch, m.ProductBatch.id == m.FmcgRecallBatch.batch_id)
            .join(m.Product, m.Product.id == m.ProductBatch.product_id)
            .where(m.FmcgRecallBatch.tenant_id == tenant_id, m.FmcgRecallBatch.recall_id == recall.id)
        )
    ).all()
    batches = []
    for link, batch, product in links:
        outlets = (
            await db.execute(
                select(
                    m.Party.id,
                    m.Party.name,
                    m.FmcgOrder.order_number,
                    m.FmcgOrder.delivered_at,
                    m.FmcgLineBatch.quantity,
                    m.FmcgLineBatch.returned_qty,
                )
                .select_from(m.FmcgLineBatch)
                .join(m.FmcgOrder, m.FmcgOrder.id == m.FmcgLineBatch.order_id)
                .join(m.Party, m.Party.id == m.FmcgOrder.customer_id)
                .where(m.FmcgLineBatch.tenant_id == tenant_id, m.FmcgLineBatch.batch_id == batch.id)
                .order_by(m.FmcgOrder.delivered_at.asc())
            )
        ).all()
        delivered = _qty(link.quantity_delivered)
        batches.append(
            {
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "product_name": product.name,
                "quantity_in_stock_now": _qty(batch.quantity),
                "quantity_delivered": delivered,
                "recovered": _qty(link.recovered_qty),
                "outstanding": _qty(max(delivered - float(link.recovered_qty or 0), 0)),
                "outlets": [
                    {
                        "outlet_id": o[0],
                        "outlet": o[1],
                        "order_number": o[2],
                        "delivered_at": o[3].isoformat() if o[3] else None,
                        "quantity": _qty(float(o[4]) - float(o[5] or 0)),
                    }
                    for o in outlets
                ],
            }
        )
    return {**_recall_row(recall), "batches": batches}


async def record_recovery(db, *, tenant_id: str, recall_id: str, batch_id: str, quantity: float, user_id) -> dict:
    recall = await _get_recall(db, tenant_id, recall_id, lock=True)
    if recall.status != "open":
        raise HTTPException(status_code=409, detail="This recall is closed")
    link = (
        await db.execute(
            select(m.FmcgRecallBatch)
            .where(
                m.FmcgRecallBatch.tenant_id == tenant_id,
                m.FmcgRecallBatch.recall_id == recall.id,
                m.FmcgRecallBatch.batch_id == batch_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="That batch is not in this recall")
    qty = _qty(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be more than zero")
    left = _qty(float(link.quantity_delivered) - float(link.recovered_qty or 0))
    if qty > left + 0.0005:
        raise HTTPException(status_code=409, detail=f"Only {left:g} is still out with outlets")
    link.recovered_qty = _qty(float(link.recovered_qty or 0) + qty)
    await _audit(
        db, tenant_id, user_id, "fmcg_recall_recovered", "fmcg_recall", recall.id,
        {"batch_id": batch_id, "quantity": qty},
    )
    await db.flush()
    return await recall_detail(db, tenant_id=tenant_id, recall_id=recall.id)


async def close_recall(db, *, tenant_id: str, recall_id: str, user_id) -> dict:
    recall = await _get_recall(db, tenant_id, recall_id, lock=True)
    if recall.status != "open":
        raise HTTPException(status_code=409, detail="This recall is already closed")
    recall.status = "closed"
    recall.closed_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "fmcg_recall_closed", "fmcg_recall", recall.id, {})
    await db.flush()
    return await recall_detail(db, tenant_id=tenant_id, recall_id=recall.id)
