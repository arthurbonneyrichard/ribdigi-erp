"""FMCG offline sync: field work saved on a device and sent when it is back online.

Supported actions: shelf audits, competitor prices, complaints and proof of delivery. Each carries a
reference the device made up. The server books each reference once: sending it again returns the first
result as ``duplicate`` and changes nothing, so a retry after a dropped connection is always safe.

Every action is checked exactly as if it had been sent live: the person's role, the territory rule,
validation, and the order must already be delivered for a proof. One that fails is rejected with the
reason and the rest of the batch still goes through; the device keeps the failed one for its owner to
fix or discard (and sending the same reference again retries it). Actions older than 72 hours, or dated
in the future, are refused. The time the action was really taken is kept on the record.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_merch as merch_svc
from app import fmcg_merch_api as merch_api
from app import fmcg_orders as orders
from app import fmcg_quality as quality_svc
from app import fmcg_quality_api as quality_api
from app import models as m

MAX_AGE = timedelta(hours=72)
MAX_FUTURE = timedelta(minutes=10)
KINDS = {"shelf_audit": "merch", "competitor_price": "merch", "complaint": "complaints", "pod": "deliver"}
MANAGERS = frozenset({"company_admin", "fmcg_manager", "super_admin"})


def _reason(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        d = exc.detail
        return str(d.get("message") if isinstance(d, dict) and d.get("message") else d)[:300]
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        return f"Invalid {'.'.join(str(x) for x in first['loc'])}: {first['msg']}"[:300]
    return "Could not be saved"


async def _run(db, *, claims: dict, kind: str, payload: dict, at: datetime) -> str:
    tenant_id, user_id = claims["tenant_id"], claims.get("sub")
    orders.job(claims, KINDS[kind])
    if kind == "shelf_audit":
        b = merch_api.AuditBody.model_validate(payload)
        out = await merch_svc.create_audit(
            db, tenant_id=tenant_id, user_id=user_id, may_audit_any=str(claims.get("role") or "") in MANAGERS, outlet_id=b.outlet_id,
            visit_id=b.visit_id, display_ok=b.display_ok, notes=b.notes, photo=b.photo, at=at,
            lines=[{"product_id": l.product_id, "present": l.present, "facings": l.facings, "shelf_price": float(l.shelf_price) if l.shelf_price is not None else None} for l in b.lines],
        )
    elif kind == "competitor_price":
        b = merch_api.PriceBody.model_validate(payload)
        out = await merch_svc.add_competitor_price(
            db, tenant_id=tenant_id, user_id=user_id, outlet_id=b.outlet_id, product_id=b.product_id, brand=b.competitor_brand,
            competitor_product=b.competitor_product, price=float(b.price), note=b.note, at=at,
        )
    elif kind == "complaint":
        b = quality_api.ComplaintBody.model_validate(payload)
        out = await quality_svc.create_complaint(
            db, tenant_id=tenant_id, customer_id=b.customer_id, order_id=b.order_id, product_id=b.product_id, batch_id=b.batch_id,
            category=b.category, description=b.description, user_id=user_id, at=at,
        )
    else:  # pod
        order_id = payload.get("order_id")
        if not isinstance(order_id, str):
            raise HTTPException(status_code=422, detail="A proof needs the order it is for")
        b = quality_api.PodBody.model_validate({k: v for k, v in payload.items() if k != "order_id"})
        out = await quality_svc.record_pod(
            db, tenant_id=tenant_id, order_id=order_id, recipient_name=b.recipient_name, signature=b.signature, photo=b.photo,
            latitude=b.latitude, longitude=b.longitude, accuracy_m=b.accuracy_m, notes=b.notes, user_id=user_id, at=at,
        )
    return out["id"]


async def sync(db: AsyncSession, *, claims: dict, actions: list[dict]) -> list[dict]:
    tenant_id, user_id = claims["tenant_id"], claims.get("sub")
    now = datetime.utcnow()
    results, seen = [], set()
    for a in actions:
        ref, kind = a["ref"], a["kind"]
        if ref in seen:
            results.append({"ref": ref, "status": "duplicate", "message": "Sent twice in the same batch"})
            continue
        seen.add(ref)
        existing = (await db.execute(select(m.FmcgOfflineRef).where(m.FmcgOfflineRef.tenant_id == tenant_id, m.FmcgOfflineRef.ref == ref).with_for_update())).scalar_one_or_none()
        if existing is not None and existing.status == "ok":
            results.append({"ref": ref, "status": "duplicate", "result_id": existing.result_id, "message": "Already saved"})
            continue
        at = a["captured_at"].replace(tzinfo=None) if a["captured_at"].tzinfo else a["captured_at"]
        status, result_id, message = "failed", None, ""
        if at < now - MAX_AGE:
            message = "Older than 72 hours, so it was not accepted"
        elif at > now + MAX_FUTURE:
            message = "Dated in the future. Check the device clock"
        else:
            try:
                async with db.begin_nested():
                    result_id = await _run(db, claims=claims, kind=kind, payload=a["payload"], at=at)
                status, message = "ok", "Saved"
            except (HTTPException, ValidationError) as exc:
                message = _reason(exc)
        row = existing or m.FmcgOfflineRef(tenant_id=tenant_id, ref=ref, kind=kind, user_id=user_id)
        row.status, row.result_id, row.message, row.captured_at, row.received_at, row.kind = status, result_id, message[:300], at, now, kind
        if existing is None:
            db.add(row)
        await db.flush()
        results.append({"ref": ref, "status": status, "result_id": result_id, "message": message})
    return results


async def log(db: AsyncSession, *, tenant_id: str, user_id: str | None, limit: int = 100) -> list[dict]:
    stmt = select(m.FmcgOfflineRef).where(m.FmcgOfflineRef.tenant_id == tenant_id)
    if user_id:
        stmt = stmt.where(m.FmcgOfflineRef.user_id == user_id)
    rows = (await db.execute(stmt.order_by(m.FmcgOfflineRef.received_at.desc()).limit(limit))).scalars().all()
    return [{"ref": r.ref, "kind": r.kind, "status": r.status, "message": r.message, "result_id": r.result_id,
             "captured_at": r.captured_at.isoformat(timespec="seconds") if r.captured_at else None, "received_at": r.received_at.isoformat(timespec="seconds")} for r in rows]
