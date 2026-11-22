"""FMCG quality: proof of delivery, goods inspections and customer complaints.

Proof of delivery keeps who signed, an optional photo and where the phone was. Inspections can
hold a batch until it passes; a failed batch stays held (reusing ``batch_holds``, so every stock-out
path refuses it). A batch that is already on a recall hold is never touched by an inspection.
Complaints can point at an order, product and batch so repeat problems on one batch are visible.
"""

from __future__ import annotations

import base64
import binascii
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_orders as orders
from app import models as m
from app import pharmacy as pharmacy_svc
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

SIGNATURE_MAX = 150_000
PHOTO_MAX = 800_000
RESULTS = ("pass", "fail", "conditional")
COMPLAINT_CATEGORIES = ("quality", "damaged", "short", "wrong", "expiry", "other")
COMPLAINT_STATUSES = ("open", "investigating", "resolved", "rejected")


def _image(data_url: str | None, *, limit: int, label: str) -> str | None:
    """Accept only a real PNG or JPEG sent as a data URL, within the size limit."""
    if not data_url:
        return None
    head, _, body = data_url.partition(",")
    if head not in ("data:image/png;base64", "data:image/jpeg;base64"):
        raise HTTPException(status_code=422, detail=f"The {label} must be a PNG or JPEG image")
    try:
        raw = base64.b64decode(body, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail=f"The {label} could not be read") from None
    if len(raw) > limit:
        raise HTTPException(status_code=413, detail=f"The {label} is too large (limit {limit // 1000} KB)")
    is_png = raw.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = raw.startswith(b"\xff\xd8\xff")
    if (head.endswith("png;base64") and not is_png) or (head.endswith("jpeg;base64") and not is_jpeg):
        raise HTTPException(status_code=422, detail=f"The {label} is not the image type it says it is")
    return data_url


# ---------------------------------------------------------------- proof of delivery

async def record_pod(
    db, *, tenant_id: str, order_id: str, recipient_name: str, signature: str | None, photo: str | None,
    latitude: float | None, longitude: float | None, accuracy_m: float | None, notes: str | None, user_id, at: datetime | None = None,
) -> dict:
    order = await orders._order(db, tenant_id, order_id, lock=True)
    if order.status != "delivered":
        raise HTTPException(status_code=409, detail="Proof can only be taken once the order is delivered")
    who = require_honest_narrative(recipient_name, label="recipient name", max_length=150)
    sig = _image(signature, limit=SIGNATURE_MAX, label="signature")
    pic = _image(photo, limit=PHOTO_MAX, label="photo")
    if not sig and not pic:
        raise HTTPException(status_code=422, detail="Take a signature or a photo")
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Send both latitude and longitude, or neither")
    existing = (
        await db.execute(
            select(m.FmcgProofOfDelivery.id).where(
                m.FmcgProofOfDelivery.tenant_id == tenant_id, m.FmcgProofOfDelivery.order_id == order.id
            )
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Proof of delivery is already recorded for this order")
    row = m.FmcgProofOfDelivery(
        tenant_id=tenant_id, order_id=order.id, recipient_name=who, signature=sig, photo=pic,
        latitude=latitude, longitude=longitude, accuracy_m=accuracy_m,
        notes=optional_honest_narrative(notes, label="notes", max_length=500), captured_by=user_id,
        **({"captured_at": at} if at else {}),
    )
    db.add(row)
    await orders._audit(
        db, tenant_id, user_id, "fmcg_pod_captured", "fmcg_order", order.id,
        {"recipient": who, "signature": bool(sig), "photo": bool(pic), "has_location": latitude is not None},
    )
    await db.flush()
    return _pod_row(row, order, images=False)


def _pod_row(row: m.FmcgProofOfDelivery, order: m.FmcgOrder, *, images: bool) -> dict:
    data = {
        "id": row.id,
        "order_id": row.order_id,
        "order_number": order.order_number,
        "recipient_name": row.recipient_name,
        "has_signature": bool(row.signature),
        "has_photo": bool(row.photo),
        "latitude": money_json(row.latitude) if row.latitude is not None else None,
        "longitude": money_json(row.longitude) if row.longitude is not None else None,
        "accuracy_m": money_json(row.accuracy_m) if row.accuracy_m is not None else None,
        "notes": row.notes,
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
    }
    if images:
        data["signature"] = row.signature
        data["photo"] = row.photo
    return data


async def get_pod(db, *, tenant_id: str, order_id: str) -> dict:
    order = await orders._order(db, tenant_id, order_id)
    row = (
        await db.execute(
            select(m.FmcgProofOfDelivery).where(
                m.FmcgProofOfDelivery.tenant_id == tenant_id, m.FmcgProofOfDelivery.order_id == order.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No proof of delivery for this order")
    return _pod_row(row, order, images=True)


async def missing_pod(db, *, tenant_id: str, days: int = 30) -> list[dict]:
    """Delivered orders with no proof, newest first. A manager chases these."""
    since = datetime.combine(date.today() - timedelta(days=max(1, min(int(days), 365))), datetime.min.time())
    rows = (
        await db.execute(
            select(m.FmcgOrder, m.Party.name)
            .join(m.Party, m.Party.id == m.FmcgOrder.customer_id)
            .outerjoin(
                m.FmcgProofOfDelivery,
                (m.FmcgProofOfDelivery.order_id == m.FmcgOrder.id)
                & (m.FmcgProofOfDelivery.tenant_id == m.FmcgOrder.tenant_id),
            )
            .where(
                m.FmcgOrder.tenant_id == tenant_id,
                m.FmcgOrder.status == "delivered",
                m.FmcgOrder.delivered_at >= since,
                m.FmcgProofOfDelivery.id.is_(None),
            )
            .order_by(m.FmcgOrder.delivered_at.desc())
            .limit(200)
        )
    ).all()
    return [
        {
            "order_id": o.id, "order_number": o.order_number, "outlet": name, "total": money_json(o.total),
            "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
        }
        for o, name in rows
    ]


# ---------------------------------------------------------------- inspections

async def _product(db, tenant_id: str, product_id: str) -> m.Product:
    row = (
        await db.execute(select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


async def _batch_of(db, tenant_id: str, batch_id: str, product_id: str) -> m.ProductBatch:
    row = (
        await db.execute(
            select(m.ProductBatch).where(m.ProductBatch.id == batch_id, m.ProductBatch.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None or row.product_id != product_id:
        raise HTTPException(status_code=404, detail="Batch not found for that product")
    return row


async def _open_hold(db, tenant_id: str, batch_id: str) -> m.BatchHold | None:
    return (
        await db.execute(
            select(m.BatchHold).where(
                m.BatchHold.tenant_id == tenant_id, m.BatchHold.batch_id == batch_id, m.BatchHold.status == "open"
            )
        )
    ).scalar_one_or_none()


async def create_inspection(
    db, *, tenant_id: str, product_id: str, batch_id: str | None, supplier_id: str | None, sample_size: float,
    packaging_ok: bool | None, label_ok: bool | None, expiry_ok: bool | None, temperature_c: float | None,
    certificate_ref: str | None, notes: str | None, hold_until_decided: bool, user_id,
) -> dict:
    product = await _product(db, tenant_id, product_id)
    if batch_id:
        await _batch_of(db, tenant_id, batch_id, product.id)
    if supplier_id:
        supplier = (
            await db.execute(
                select(m.Party).where(m.Party.id == supplier_id, m.Party.tenant_id == tenant_id, m.Party.kind == "supplier")
            )
        ).scalar_one_or_none()
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
    if hold_until_decided and not batch_id:
        raise HTTPException(status_code=422, detail="Pick a batch to hold it until the inspection is decided")
    row = m.FmcgQcInspection(
        tenant_id=tenant_id,
        inspection_number=await orders._next_number(db, tenant_id, m.FmcgQcInspection, "QC"),
        product_id=product.id, batch_id=batch_id, supplier_id=supplier_id, sample_size=sample_size,
        packaging_ok=packaging_ok, label_ok=label_ok, expiry_ok=expiry_ok, temperature_c=temperature_c,
        certificate_ref=optional_honest_narrative(certificate_ref, label="certificate reference", max_length=120),
        notes=optional_honest_narrative(notes, label="notes", max_length=1000), status="pending", created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if hold_until_decided and batch_id:
        if await _open_hold(db, tenant_id, batch_id) is None:
            await pharmacy_svc.create_hold(
                db, tenant_id=tenant_id, created_by=user_id, batch_id=batch_id, hold_type="quarantine",
                reason=f"Held for inspection {row.inspection_number}",
            )
            row.placed_hold = True
    await orders._audit(
        db, tenant_id, user_id, "fmcg_qc_opened", "fmcg_qc_inspection", row.id,
        {"number": row.inspection_number, "product_id": product.id, "batch_id": batch_id, "held": row.placed_hold},
    )
    await db.flush()
    return await _present(db, row)


async def decide_inspection(
    db, *, tenant_id: str, inspection_id: str, result: str, note: str | None, rejected_qty: float, user_id
) -> dict:
    if result not in RESULTS:
        raise HTTPException(status_code=422, detail=f"result must be one of: {', '.join(RESULTS)}")
    row = (
        await db.execute(
            select(m.FmcgQcInspection)
            .where(m.FmcgQcInspection.id == inspection_id, m.FmcgQcInspection.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="This inspection is already decided")
    failed_checks = [n for n, v in (("packaging", row.packaging_ok), ("label", row.label_ok), ("expiry date", row.expiry_ok)) if v is False]
    if result == "pass" and failed_checks:
        raise HTTPException(
            status_code=409,
            detail={"code": "CHECK_FAILED", "message": f"Cannot pass: {', '.join(failed_checks)} failed its check"},
        )
    text = optional_honest_narrative(note, label="decision note", max_length=1000)
    if result in ("fail", "conditional") and not text:
        raise HTTPException(status_code=422, detail="Say why")
    if rejected_qty and result != "fail":
        raise HTTPException(status_code=422, detail="Only a failed inspection has rejected quantity")
    if result == "fail" and row.batch_id:
        batch = await db.get(m.ProductBatch, row.batch_id)
        if rejected_qty > float(batch.quantity or 0) + 0.0005:
            raise HTTPException(status_code=409, detail=f"The batch only has {float(batch.quantity or 0):g}")
    if row.batch_id:
        hold = await _open_hold(db, tenant_id, row.batch_id)
        if result == "fail":
            if hold is None:
                await pharmacy_svc.create_hold(
                    db, tenant_id=tenant_id, created_by=user_id, batch_id=row.batch_id, hold_type="quarantine",
                    reason=f"Failed inspection {row.inspection_number}: {text}",
                )
                row.placed_hold = True
        elif hold is not None and row.placed_hold and hold.hold_type == "quarantine":
            # Only release a hold this inspection put there; a recall or someone else's hold stays.
            await pharmacy_svc.release_hold(db, tenant_id=tenant_id, hold_id=hold.id)
    row.status = {"pass": "passed", "fail": "failed", "conditional": "conditional"}[result]
    row.decision_note = text
    row.rejected_qty = rejected_qty if result == "fail" else 0
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    await orders._audit(
        db, tenant_id, user_id, "fmcg_qc_decided", "fmcg_qc_inspection", row.id,
        {"result": row.status, "note": text, "rejected_qty": float(row.rejected_qty or 0)},
    )
    await db.flush()
    return await _present(db, row)


async def _present(db, row: m.FmcgQcInspection) -> dict:
    product = await db.get(m.Product, row.product_id)
    batch = await db.get(m.ProductBatch, row.batch_id) if row.batch_id else None
    supplier = await db.get(m.Party, row.supplier_id) if row.supplier_id else None
    return {
        "id": row.id, "inspection_number": row.inspection_number, "status": row.status,
        "product_id": row.product_id, "product_name": product.name if product else None,
        "batch_id": row.batch_id, "batch_number": batch.batch_number if batch else None,
        "supplier_id": row.supplier_id, "supplier": supplier.name if supplier else None,
        "sample_size": money_json(row.sample_size), "packaging_ok": row.packaging_ok, "label_ok": row.label_ok,
        "expiry_ok": row.expiry_ok, "temperature_c": money_json(row.temperature_c) if row.temperature_c is not None else None,
        "certificate_ref": row.certificate_ref, "notes": row.notes, "rejected_qty": money_json(row.rejected_qty),
        "held": row.placed_hold, "decision_note": row.decision_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


async def list_inspections(db, *, tenant_id: str, status: str | None = None) -> list[dict]:
    stmt = select(m.FmcgQcInspection).where(m.FmcgQcInspection.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(m.FmcgQcInspection.status == status)
    rows = (await db.execute(stmt.order_by(m.FmcgQcInspection.created_at.desc()).limit(200))).scalars().all()
    return [await _present(db, r) for r in rows]


async def supplier_quality(db, *, tenant_id: str) -> list[dict]:
    """Pass and fail history per supplier, worst fail rate first."""
    rows = (
        await db.execute(
            select(m.Party.id, m.Party.name, m.FmcgQcInspection.status, func.count())
            .join(m.Party, m.Party.id == m.FmcgQcInspection.supplier_id)
            .where(m.FmcgQcInspection.tenant_id == tenant_id, m.FmcgQcInspection.status != "pending")
            .group_by(m.Party.id, m.Party.name, m.FmcgQcInspection.status)
        )
    ).all()
    book: dict[str, dict] = {}
    for sid, name, status, n in rows:
        entry = book.setdefault(sid, {"supplier_id": sid, "supplier": name, "passed": 0, "conditional": 0, "failed": 0})
        entry[status] = int(n)
    out = []
    for entry in book.values():
        total = entry["passed"] + entry["conditional"] + entry["failed"]
        entry["inspected"] = total
        entry["fail_rate_pct"] = round(100 * entry["failed"] / total, 1) if total else 0.0
        out.append(entry)
    return sorted(out, key=lambda e: (-e["fail_rate_pct"], -e["inspected"]))


# ---------------------------------------------------------------- complaints

async def create_complaint(
    db, *, tenant_id: str, customer_id: str | None, order_id: str | None, product_id: str | None,
    batch_id: str | None, category: str, description: str, user_id, at: datetime | None = None,
) -> dict:
    if category not in COMPLAINT_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of: {', '.join(COMPLAINT_CATEGORIES)}")
    text = require_honest_narrative(description, label="description", max_length=2000)
    if customer_id:
        await orders._outlet(db, tenant_id, customer_id)
    if order_id:
        order = await orders._order(db, tenant_id, order_id)
        customer_id = customer_id or order.customer_id
    if product_id:
        await _product(db, tenant_id, product_id)
    if batch_id:
        if not product_id:
            raise HTTPException(status_code=422, detail="Pick the product for that batch")
        await _batch_of(db, tenant_id, batch_id, product_id)
    row = m.FmcgComplaint(
        tenant_id=tenant_id, complaint_number=await orders._next_number(db, tenant_id, m.FmcgComplaint, "CP"),
        customer_id=customer_id, order_id=order_id, product_id=product_id, batch_id=batch_id,
        category=category, description=text, status="open", created_by=user_id,
        **({"created_at": at} if at else {}),
    )
    db.add(row)
    await db.flush()
    await orders._audit(
        db, tenant_id, user_id, "fmcg_complaint_opened", "fmcg_complaint", row.id,
        {"category": category, "batch_id": batch_id},
    )
    return await _complaint_row(db, row)


async def _complaint_row(db, row: m.FmcgComplaint) -> dict:
    party = await db.get(m.Party, row.customer_id) if row.customer_id else None
    product = await db.get(m.Product, row.product_id) if row.product_id else None
    batch = await db.get(m.ProductBatch, row.batch_id) if row.batch_id else None
    same_batch = 0
    if row.batch_id:
        same_batch = int(
            (
                await db.execute(
                    select(func.count()).select_from(m.FmcgComplaint).where(
                        m.FmcgComplaint.tenant_id == row.tenant_id, m.FmcgComplaint.batch_id == row.batch_id
                    )
                )
            ).scalar_one()
        )
    return {
        "id": row.id, "complaint_number": row.complaint_number, "status": row.status, "category": row.category,
        "description": row.description, "resolution": row.resolution,
        "customer_id": row.customer_id, "outlet": party.name if party else None,
        "order_id": row.order_id, "product_id": row.product_id, "product_name": product.name if product else None,
        "batch_id": row.batch_id, "batch_number": batch.batch_number if batch else None,
        "complaints_on_this_batch": same_batch,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


async def list_complaints(db, *, tenant_id: str, status: str | None = None) -> list[dict]:
    stmt = select(m.FmcgComplaint).where(m.FmcgComplaint.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(m.FmcgComplaint.status == status)
    rows = (await db.execute(stmt.order_by(m.FmcgComplaint.created_at.desc()).limit(200))).scalars().all()
    return [await _complaint_row(db, r) for r in rows]


async def set_complaint_status(
    db, *, tenant_id: str, complaint_id: str, status: str, resolution: str | None, user_id
) -> dict:
    if status not in COMPLAINT_STATUSES or status == "open":
        raise HTTPException(status_code=422, detail="status must be investigating, resolved or rejected")
    row = (
        await db.execute(
            select(m.FmcgComplaint)
            .where(m.FmcgComplaint.id == complaint_id, m.FmcgComplaint.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if row.status in ("resolved", "rejected"):
        raise HTTPException(status_code=409, detail="This complaint is already closed")
    if status in ("resolved", "rejected"):
        row.resolution = require_honest_narrative(resolution, label="resolution", max_length=2000)
        row.resolved_at = datetime.utcnow()
    row.status = status
    await orders._audit(
        db, tenant_id, user_id, "fmcg_complaint_status", "fmcg_complaint", row.id,
        {"status": status, "resolution": row.resolution},
    )
    await db.flush()
    return await _complaint_row(db, row)
