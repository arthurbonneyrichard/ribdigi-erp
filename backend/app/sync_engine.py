"""Stage 164 sync queue engine — push/pull/ack/conflicts + status honesty."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import offline_devices as offline_devices_svc
from app.schemas import PosSaleCreate


ALLOWED_PUSH_OP_TYPES = {"pos_sale", "ping"}
ALLOWED_PULL_OP_TYPES = {"catalog_products", "sync_status"}


def _payload_fingerprint(payload: dict | None) -> str:
    raw = json.dumps(payload or {}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def serialize_queue_item(row: m.SyncQueueItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "device_id": row.device_id,
        "direction": row.direction,
        "op_type": row.op_type,
        "client_op_id": row.client_op_id,
        "payload": row.payload or {},
        "status": row.status,
        "result_entity_id": row.result_entity_id,
        "result_payload": row.result_payload,
        "error": row.error,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        "applied_at": row.applied_at.isoformat() + "Z" if row.applied_at else None,
        "acked_at": row.acked_at.isoformat() + "Z" if row.acked_at else None,
    }


def serialize_conflict(row: m.SyncConflict) -> dict[str, Any]:
    return {
        "id": row.id,
        "queue_item_id": row.queue_item_id,
        "device_id": row.device_id,
        "op_type": row.op_type,
        "client_op_id": row.client_op_id,
        "client_payload": row.client_payload or {},
        "server_snapshot": row.server_snapshot or {},
        "status": row.status,
        "resolution": row.resolution,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() + "Z" if row.resolved_at else None,
    }


def _conflict_was_applied(item: m.SyncQueueItem | None, snapshot: dict | None) -> bool:
    """True when the original op already succeeded — never double-post pos_sale."""
    if item is not None:
        if item.applied_at is not None:
            return True
        if item.result_entity_id:
            return True
        if item.status == "applied":
            return True
    snap = snapshot or {}
    qi = snap.get("queue_item") if isinstance(snap, dict) else None
    if isinstance(qi, dict):
        if qi.get("applied_at") or qi.get("result_entity_id"):
            return True
        if qi.get("status") == "applied":
            return True
    return False


async def require_active_device(
    db: AsyncSession, tenant_id: str, device_id: str
) -> m.OfflineDevice:
    if not (device_id or "").strip():
        raise HTTPException(status_code=400, detail="device_id is required")
    device = await offline_devices_svc.get_device(db, tenant_id, device_id.strip())
    if device.revoked_at is not None:
        raise HTTPException(status_code=409, detail="Offline device is revoked")
    device.last_seen_at = datetime.utcnow()
    device.updated_at = datetime.utcnow()
    await db.flush()
    return device


async def sync_status(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Stage 164 Q1 — real queue counts; never fabricate success."""
    pending_pushes = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.SyncQueueItem)
                .where(
                    m.SyncQueueItem.tenant_id == tenant_id,
                    m.SyncQueueItem.direction == "push",
                    m.SyncQueueItem.status.in_(["pending", "failed"]),
                )
            )
        ).scalar_one()
        or 0
    )
    pending_pulls = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.SyncQueueItem)
                .where(
                    m.SyncQueueItem.tenant_id == tenant_id,
                    m.SyncQueueItem.direction == "pull",
                    m.SyncQueueItem.status == "pending",
                )
            )
        ).scalar_one()
        or 0
    )
    conflict_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.SyncConflict)
                .where(
                    m.SyncConflict.tenant_id == tenant_id,
                    m.SyncConflict.status == "open",
                )
            )
        ).scalar_one()
        or 0
    )
    last_sync_at = (
        await db.execute(
            select(func.max(m.SyncQueueItem.applied_at)).where(
                m.SyncQueueItem.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    return {
        "sync_enabled": True,
        "queue_depth": pending_pushes + pending_pulls,
        "pending_pushes": pending_pushes,
        "pending_pulls": pending_pulls,
        "last_sync_at": last_sync_at,
        "conflict_count": conflict_count,
        "message": (
            "Stage 164–166 sync queue APIs are live (push/pull/ack/conflicts/resolve). "
            "Idempotent offline POS path requires client_request_id. "
            "Hold soft reserve (Stage 166 S1) is optional via reserve_stock. "
            "accept_client may re-apply only when the original op was never applied. "
            "Full Offline Complete remains deferred."
        ),
    }


async def _get_by_client_op(
    db: AsyncSession, tenant_id: str, client_op_id: str
) -> m.SyncQueueItem | None:
    return (
        await db.execute(
            select(m.SyncQueueItem).where(
                m.SyncQueueItem.tenant_id == tenant_id,
                m.SyncQueueItem.client_op_id == client_op_id,
            )
        )
    ).scalar_one_or_none()


async def _open_conflict(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str | None,
    queue_item_id: str | None,
    op_type: str,
    client_op_id: str | None,
    client_payload: dict,
    server_snapshot: dict,
) -> m.SyncConflict:
    row = m.SyncConflict(
        tenant_id=tenant_id,
        queue_item_id=queue_item_id,
        device_id=device_id,
        op_type=op_type,
        client_op_id=client_op_id,
        client_payload=client_payload or {},
        server_snapshot=server_snapshot or {},
        status="open",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def push_ops(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    claims: dict,
    device_id: str,
    ops: list[dict],
) -> dict[str, Any]:
    """Stage 164 P1 — accept device-scoped push ops; apply pos_sale idempotently."""
    if not isinstance(ops, list) or not ops:
        raise HTTPException(status_code=400, detail="ops must be a non-empty list")
    if len(ops) > 50:
        raise HTTPException(status_code=400, detail="ops batch limit is 50")

    device = await require_active_device(db, tenant_id, device_id)
    results: list[dict[str, Any]] = []

    for raw in ops:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="each op must be an object")
        client_op_id = str(raw.get("client_op_id") or "").strip()
        op_type = str(raw.get("op_type") or "").strip().lower()
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        if len(client_op_id) < 8:
            raise HTTPException(status_code=400, detail="client_op_id must be at least 8 characters")
        if op_type not in ALLOWED_PUSH_OP_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"unsupported push op_type: {op_type}",
            )

        existing = await _get_by_client_op(db, tenant_id, client_op_id)
        if existing:
            if _payload_fingerprint(existing.payload) != _payload_fingerprint(payload):
                conflict = await _open_conflict(
                    db,
                    tenant_id=tenant_id,
                    device_id=device.id,
                    queue_item_id=existing.id,
                    op_type=op_type,
                    client_op_id=client_op_id,
                    client_payload=_json_safe(payload),
                    server_snapshot=_json_safe(
                        {
                            "queue_item": serialize_queue_item(existing),
                            "reason": "client_op_id reuse with different payload",
                        }
                    ),
                )
                existing.status = "conflict"
                existing.updated_at = datetime.utcnow()
                existing.error = "payload conflict on client_op_id reuse"
                await db.flush()
                results.append(
                    {
                        "client_op_id": client_op_id,
                        "status": "conflict",
                        "queue_item": serialize_queue_item(existing),
                        "conflict": serialize_conflict(conflict),
                        "replayed": True,
                    }
                )
                continue
            results.append(
                {
                    "client_op_id": client_op_id,
                    "status": existing.status,
                    "queue_item": serialize_queue_item(existing),
                    "replayed": True,
                }
            )
            continue

        now = datetime.utcnow()
        item = m.SyncQueueItem(
            tenant_id=tenant_id,
            device_id=device.id,
            direction="push",
            op_type=op_type,
            client_op_id=client_op_id,
            payload=payload,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        await db.flush()

        try:
            if op_type == "ping":
                item.status = "applied"
                item.applied_at = datetime.utcnow()
                item.result_payload = {"pong": True, "device_id": device.id}
            elif op_type == "pos_sale":
                sale_out = await _apply_pos_sale_op(
                    db, claims=claims, user_id=user_id, payload=payload
                )
                item.status = "applied"
                item.applied_at = datetime.utcnow()
                item.result_entity_id = sale_out.get("id")
                item.result_payload = _json_safe(sale_out)
            item.updated_at = datetime.utcnow()
            await db.flush()
            results.append(
                {
                    "client_op_id": client_op_id,
                    "status": item.status,
                    "queue_item": serialize_queue_item(item),
                    "replayed": False,
                }
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            item.status = "failed"
            item.error = detail
            item.updated_at = datetime.utcnow()
            await db.flush()
            results.append(
                {
                    "client_op_id": client_op_id,
                    "status": "failed",
                    "queue_item": serialize_queue_item(item),
                    "error": detail,
                    "replayed": False,
                }
            )

    await db.flush()
    return {"device_id": device.id, "results": results}


async def _apply_pos_sale_op(
    db: AsyncSession, *, claims: dict, user_id: str, payload: dict
) -> dict[str, Any]:
    """Stage 164 I1 — apply offline POS sale via online integrity path."""
    from app.pos_record import record_pos_sale

    client_request_id = str(payload.get("client_request_id") or "").strip()
    if len(client_request_id) < 8:
        raise HTTPException(
            status_code=400,
            detail="pos_sale payload requires client_request_id (min 8 chars)",
        )
    body = dict(payload)
    body["client_request_id"] = client_request_id
    try:
        sale_payload = PosSaleCreate.model_validate(body)
    except Exception as exc:  # pydantic ValidationError
        raise HTTPException(status_code=400, detail=f"invalid pos_sale payload: {exc}") from exc

    # Ensure sync path uses the same idempotency key as the sale row.
    if not sale_payload.client_request_id:
        raise HTTPException(status_code=400, detail="client_request_id required")

    return await record_pos_sale(db, claims=claims, payload=sale_payload, commit=False)


async def pull_ops(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str,
    limit: int = 50,
    include_catalog: bool = True,
) -> dict[str, Any]:
    """Stage 164 L1 — pending pull ops + optional bounded catalog snapshot."""
    device = await require_active_device(db, tenant_id, device_id)
    window = max(1, min(int(limit or 50), 100))

    pending = list(
        (
            await db.execute(
                select(m.SyncQueueItem)
                .where(
                    m.SyncQueueItem.tenant_id == tenant_id,
                    m.SyncQueueItem.direction == "pull",
                    m.SyncQueueItem.status == "pending",
                    (m.SyncQueueItem.device_id == device.id)
                    | (m.SyncQueueItem.device_id.is_(None)),
                )
                .order_by(m.SyncQueueItem.created_at.asc())
                .limit(window)
            )
        )
        .scalars()
        .all()
    )

    catalog_op = None
    if include_catalog:
        products = list(
            (
                await db.execute(
                    select(m.Product)
                    .where(
                        m.Product.tenant_id == tenant_id,
                        m.Product.is_active.is_(True),
                    )
                    .order_by(m.Product.name.asc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        now = datetime.utcnow()
        client_op_id = f"pull-catalog-{device.id}-{now.strftime('%Y%m%d%H%M%S')}"
        from app.inventory import available_qty

        catalog_payload = {
            "products": [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "barcode": getattr(p, "barcode", None),
                    "selling_price": float(p.selling_price or 0),
                    "stock_qty": float(getattr(p, "stock_qty", 0) or 0),
                    "reserved_qty": float(getattr(p, "reserved_qty", 0) or 0),
                    "available_qty": available_qty(
                        getattr(p, "stock_qty", 0), getattr(p, "reserved_qty", 0)
                    ),
                }
                for p in products
            ],
            "bounded": True,
            "limit": 100,
            # Offline clients must treat stock as non-authoritative (Stage 166 C1).
            "stock_authoritative": False,
            "as_of": now.isoformat() + "Z",
        }
        catalog_op = m.SyncQueueItem(
            tenant_id=tenant_id,
            device_id=device.id,
            direction="pull",
            op_type="catalog_products",
            client_op_id=client_op_id,
            payload=catalog_payload,
            status="pending",
            result_payload=catalog_payload,
            created_at=now,
            updated_at=now,
        )
        db.add(catalog_op)
        await db.flush()
        pending.append(catalog_op)

    return {
        "device_id": device.id,
        "ops": [serialize_queue_item(r) for r in pending],
        "count": len(pending),
    }


async def ack_ops(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str,
    op_ids: list[str],
) -> dict[str, Any]:
    """Stage 164 A1 — mark pull/push results as acked by the device."""
    if not isinstance(op_ids, list) or not op_ids:
        raise HTTPException(status_code=400, detail="op_ids must be a non-empty list")
    if len(op_ids) > 100:
        raise HTTPException(status_code=400, detail="op_ids batch limit is 100")

    device = await require_active_device(db, tenant_id, device_id)
    now = datetime.utcnow()
    acked: list[dict[str, Any]] = []
    for raw_id in op_ids:
        op_id = str(raw_id or "").strip()
        if not op_id:
            continue
        row = (
            await db.execute(
                select(m.SyncQueueItem).where(
                    m.SyncQueueItem.id == op_id,
                    m.SyncQueueItem.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail=f"sync op not found: {op_id}")
        if row.device_id and row.device_id != device.id:
            raise HTTPException(status_code=403, detail="sync op belongs to another device")
        # Ack records device receipt. Does not invent apply success for failed ops.
        if row.status in {"applied", "pending"} and row.direction == "pull":
            row.status = "acked"
        elif row.status == "applied":
            row.status = "acked"
        row.acked_at = now
        row.updated_at = now
        acked.append(serialize_queue_item(row))

    await db.flush()
    return {"device_id": device.id, "acked": acked, "count": len(acked)}


async def list_conflicts(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = "open",
) -> list[m.SyncConflict]:
    """Stage 164 C1 — list conflicts (default open only)."""
    q = select(m.SyncConflict).where(m.SyncConflict.tenant_id == tenant_id)
    if status is not None:
        wanted = str(status).strip().lower()
        if wanted not in {"open", "resolved", "all"}:
            raise HTTPException(status_code=400, detail="status must be open, resolved, or all")
        if wanted != "all":
            q = q.where(m.SyncConflict.status == wanted)
    q = q.order_by(m.SyncConflict.created_at.desc())
    return list((await db.execute(q)).scalars().all())


RESOLVE_ACTIONS = {"keep_server", "accept_client", "dismiss"}


async def resolve_conflict(
    db: AsyncSession,
    *,
    tenant_id: str,
    conflict_id: str,
    resolution: str,
    claims: dict | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Stage 165 R1 / Stage 166 A1 — resolve conflict; safe accept_client re-apply only."""
    action = (resolution or "").strip().lower()
    if action not in RESOLVE_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail="resolution must be keep_server, accept_client, or dismiss",
        )
    row = (
        await db.execute(
            select(m.SyncConflict).where(
                m.SyncConflict.id == conflict_id,
                m.SyncConflict.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sync conflict not found")

    if row.status == "resolved":
        out = serialize_conflict(row)
        out["reapplied"] = False
        out["reapply_blocked_reason"] = "already_resolved"
        out["message"] = "Conflict already resolved."
        return out

    item: m.SyncQueueItem | None = None
    if row.queue_item_id:
        item = (
            await db.execute(
                select(m.SyncQueueItem).where(
                    m.SyncQueueItem.id == row.queue_item_id,
                    m.SyncQueueItem.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

    reapplied = False
    reapply_blocked_reason: str | None = None
    reapply_queue_item: dict | None = None
    message = "Conflict marked resolved."

    if action == "accept_client":
        if _conflict_was_applied(item, row.server_snapshot):
            # Honesty: never double-post an already-applied POS (or other) op.
            reapply_blocked_reason = "original_op_already_applied"
            message = (
                "Conflict resolved with accept_client. Client payload was not re-applied "
                "because the original op was already applied (Stage 166 A1 — avoids double-post)."
            )
        else:
            # Safe path: original never applied — re-apply under a new client_op_id.
            reapply_op_id = f"reapply-{row.id}"
            if len(reapply_op_id) > 80:
                reapply_op_id = reapply_op_id[:80]
            existing_reapply = await _get_by_client_op(db, tenant_id, reapply_op_id)
            if existing_reapply:
                reapplied = existing_reapply.status == "applied"
                reapply_queue_item = serialize_queue_item(existing_reapply)
                message = (
                    "Conflict resolved; prior accept_client re-apply reused (idempotent)."
                )
            else:
                now = datetime.utcnow()
                new_item = m.SyncQueueItem(
                    tenant_id=tenant_id,
                    device_id=row.device_id,
                    direction="push",
                    op_type=row.op_type,
                    client_op_id=reapply_op_id,
                    payload=row.client_payload or {},
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_item)
                await db.flush()
                try:
                    if row.op_type == "ping":
                        new_item.status = "applied"
                        new_item.applied_at = datetime.utcnow()
                        new_item.result_payload = {"pong": True, "reapplied_from": row.id}
                    elif row.op_type == "pos_sale":
                        if not claims:
                            raise HTTPException(
                                status_code=400,
                                detail="claims required to re-apply pos_sale",
                            )
                        sale_out = await _apply_pos_sale_op(
                            db,
                            claims=claims,
                            user_id=user_id or claims.get("sub"),
                            payload=row.client_payload or {},
                        )
                        new_item.status = "applied"
                        new_item.applied_at = datetime.utcnow()
                        new_item.result_entity_id = sale_out.get("id")
                        new_item.result_payload = _json_safe(sale_out)
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"cannot re-apply unsupported op_type: {row.op_type}",
                        )
                    new_item.updated_at = datetime.utcnow()
                    await db.flush()
                    reapplied = True
                    reapply_queue_item = serialize_queue_item(new_item)
                    message = (
                        "Conflict resolved; client payload re-applied under a new client_op_id "
                        "(Stage 166 A1)."
                    )
                except HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                    new_item.status = "failed"
                    new_item.error = detail
                    new_item.updated_at = datetime.utcnow()
                    await db.flush()
                    reapply_blocked_reason = f"reapply_failed:{detail}"
                    reapply_queue_item = serialize_queue_item(new_item)
                    message = (
                        "Conflict resolved, but accept_client re-apply failed "
                        f"({detail})."
                    )
    elif action == "keep_server":
        message = (
            "Conflict marked resolved (keep_server). Client payload was not re-applied "
            "(Stage 165 R1 honesty)."
        )
    else:
        message = (
            "Conflict dismissed. Client payload was not re-applied "
            "(Stage 165 R1 honesty)."
        )

    row.status = "resolved"
    row.resolution = action
    row.resolved_at = datetime.utcnow()
    if item and item.status == "conflict":
        item.status = "acked"
        item.error = (item.error or "") + f"; conflict resolved via {action}"
        item.updated_at = datetime.utcnow()
        item.acked_at = datetime.utcnow()
    await db.flush()

    out = serialize_conflict(row)
    out["reapplied"] = reapplied
    out["reapply_blocked_reason"] = reapply_blocked_reason
    out["reapply_queue_item"] = reapply_queue_item
    out["message"] = message
    return out
