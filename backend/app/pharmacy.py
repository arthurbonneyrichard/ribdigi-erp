"""Pharmacy layer — catalog Rx flag, Rx statuses, and lot holds.

Not a hospital HIS: no clinics, diagnosis, OTA, or pharmacist license.
Tenant isolation is always ``tenant_id``. Prescription and lot-hold APIs are
pharmacy-industry only; catalog fields persist on products for any industry.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.packages import canonicalize_industry
from app.rbac import is_platform_role

RX_STATUS_ALIASES = {
    "recorded": "received",
    "voided": "cancelled",
    "partial": "partially_dispensed",
}
RX_STATUSES = frozenset(
    {"received", "review", "approved", "partially_dispensed", "dispensed", "cancelled"}
)
RX_OPEN_QUEUE = frozenset({"received", "review", "approved", "partially_dispensed"})
RX_DISPENSE_OK = frozenset({"approved", "partially_dispensed"})
RX_TRANSITIONS = {
    "received": frozenset({"review", "approved", "cancelled"}),
    "review": frozenset({"approved", "cancelled", "received"}),
    "approved": frozenset({"partially_dispensed", "dispensed", "cancelled"}),
    "partially_dispensed": frozenset({"dispensed", "cancelled"}),
    "dispensed": frozenset(),
    "cancelled": frozenset(),
}
HOLD_TYPES = frozenset({"quarantine", "recall"})


def canonicalize_rx_status(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    return RX_STATUS_ALIASES.get(key, key)


def assert_pharmacy_industry(claims: dict) -> None:
    """403 unless the live tenant industry is pharmacy (platform roles bypass)."""
    if is_platform_role(claims.get("role")):
        return
    industry = canonicalize_industry(claims.get("industry"))
    if industry != "pharmacy":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "INDUSTRY_MODULE_DISABLED",
                "message": (
                    "Prescriptions are only available for pharmacy tenants. "
                    "This is a catalog/Rx record, not a hospital or clinic module."
                ),
                "module": "inventory",
                "industry": industry,
            },
        )


def serialize_item(row: m.PrescriptionItem, *, product_name: str | None = None) -> dict:
    qty = money_json(row.quantity)
    dispensed = money_json(getattr(row, "qty_dispensed", 0) or 0)
    return {
        "id": row.id,
        "product_id": row.product_id,
        "product_name": product_name,
        "variant_id": row.variant_id,
        "quantity": qty,
        "qty_dispensed": dispensed,
        "qty_remaining": money_json(max(qty - dispensed, 0)),
        "dosage_text": row.dosage_text,
        "notes": row.notes,
    }


def serialize_attachment(row: m.PrescriptionAttachment) -> dict:
    return {
        "id": row.id,
        "prescription_id": row.prescription_id,
        "content_type": row.content_type,
        "original_filename": row.original_filename,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_prescription(
    row: m.Prescription,
    *,
    items: list[dict] | None = None,
    customer_name: str | None = None,
    sale_number: str | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    approved_at = getattr(row, "approved_at", None)
    dispensed_at = getattr(row, "dispensed_at", None)
    return {
        "id": row.id,
        "rx_number": row.rx_number,
        "customer_id": row.customer_id,
        "customer_name": customer_name,
        "sale_id": row.sale_id,
        "sale_number": sale_number,
        "prescriber_name": row.prescriber_name,
        "notes": row.notes,
        "status": canonicalize_rx_status(row.status),
        "created_by": row.created_by,
        "approved_by": getattr(row, "approved_by", None),
        "approved_at": approved_at.isoformat() if approved_at else None,
        "dispensed_at": dispensed_at.isoformat() if dispensed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "items": items if items is not None else [],
        "attachments": attachments if attachments is not None else [],
    }


def serialize_hold(
    row: m.BatchHold,
    *,
    batch_number: str | None = None,
    product_id: str | None = None,
    product_name: str | None = None,
    expiry_date: datetime | None = None,
) -> dict:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "batch_number": batch_number,
        "product_id": product_id,
        "product_name": product_name,
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
        "hold_type": row.hold_type,
        "status": row.status,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "released_at": row.released_at.isoformat() if row.released_at else None,
    }


async def allocate_rx_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"RX-{year}-"
    count = (
        await db.execute(
            select(func.count()).select_from(m.Prescription).where(m.Prescription.tenant_id == tenant_id)
        )
    ).scalar_one()
    start = int(count or 0) + 1
    for n in range(start, start + 10_000):
        candidate = f"{prefix}{n:04d}"
        exists = (
            await db.execute(
                select(m.Prescription.id).where(
                    m.Prescription.tenant_id == tenant_id,
                    m.Prescription.rx_number == candidate,
                )
            )
        ).scalar_one_or_none()
        if not exists:
            return candidate
    raise HTTPException(status_code=500, detail="Unable to allocate prescription number")


async def _product_names(db: AsyncSession, tenant_id: str, product_ids: set[str]) -> dict[str, str]:
    if not product_ids:
        return {}
    rows = (
        await db.execute(
            select(m.Product.id, m.Product.name).where(
                m.Product.tenant_id == tenant_id,
                m.Product.id.in_(list(product_ids)),
            )
        )
    ).all()
    return {pid: name for pid, name in rows}


async def _hydrate(db: AsyncSession, tenant_id: str, row: m.Prescription) -> dict:
    items = list(
        (
            await db.execute(
                select(m.PrescriptionItem)
                .where(
                    m.PrescriptionItem.tenant_id == tenant_id,
                    m.PrescriptionItem.prescription_id == row.id,
                )
                .order_by(m.PrescriptionItem.id.asc())
            )
        ).scalars().all()
    )
    names = await _product_names(db, tenant_id, {i.product_id for i in items})
    customer_name = None
    if row.customer_id:
        party = (
            await db.execute(
                select(m.Party.name).where(
                    m.Party.id == row.customer_id,
                    m.Party.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        customer_name = party
    sale_number = None
    if row.sale_id:
        inv = (
            await db.execute(
                select(m.SalesInvoice.invoice_number).where(
                    m.SalesInvoice.id == row.sale_id,
                    m.SalesInvoice.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        sale_number = inv
    attachments: list[dict] = []
    from app import schema_compat as schema_compat_svc

    if await schema_compat_svc.table_column_names(db, "prescription_attachments"):
        att_rows = list(
            (
                await db.execute(
                    select(m.PrescriptionAttachment)
                    .where(
                        m.PrescriptionAttachment.tenant_id == tenant_id,
                        m.PrescriptionAttachment.prescription_id == row.id,
                    )
                    .order_by(m.PrescriptionAttachment.created_at.asc())
                )
            ).scalars().all()
        )
        attachments = [serialize_attachment(a) for a in att_rows]
    return serialize_prescription(
        row,
        items=[serialize_item(i, product_name=names.get(i.product_id)) for i in items],
        customer_name=customer_name,
        sale_number=sale_number,
        attachments=attachments,
    )


def _status_match_values(canonical: str) -> list[str]:
    if canonical == "received":
        return ["received", "recorded"]
    if canonical == "cancelled":
        return ["cancelled", "voided"]
    return [canonical]


async def list_prescriptions(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = (
        select(m.Prescription)
        .where(m.Prescription.tenant_id == tenant_id)
        .order_by(m.Prescription.created_at.desc())
        .limit(max(1, min(int(limit or 200), 500)))
    )
    if status:
        key = canonicalize_rx_status(status)
        if key not in RX_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of: {', '.join(sorted(RX_STATUSES))}",
            )
        stmt = stmt.where(m.Prescription.status.in_(_status_match_values(key)))
    rows = list((await db.execute(stmt)).scalars().all())
    return [await _hydrate(db, tenant_id, row) for row in rows]


async def queue_counts(db: AsyncSession, tenant_id: str) -> dict[str, int]:
    rows = (
        await db.execute(
            select(m.Prescription.status, func.count())
            .where(m.Prescription.tenant_id == tenant_id)
            .group_by(m.Prescription.status)
        )
    ).all()
    counts = {key: 0 for key in RX_STATUSES}
    for raw, n in rows:
        counts[canonicalize_rx_status(raw)] = counts.get(canonicalize_rx_status(raw), 0) + int(n or 0)
    counts["open"] = sum(counts[k] for k in RX_OPEN_QUEUE)
    return counts


async def get_prescription(db: AsyncSession, *, tenant_id: str, prescription_id: str) -> dict:
    row = (
        await db.execute(
            select(m.Prescription).where(
                m.Prescription.id == prescription_id,
                m.Prescription.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return await _hydrate(db, tenant_id, row)


async def create_prescription(
    db: AsyncSession,
    *,
    tenant_id: str,
    created_by: str | None,
    customer_id: str | None,
    sale_id: str | None,
    prescriber_name: str | None,
    notes: str | None,
    items: list[dict],
) -> m.Prescription:
    if not items:
        raise HTTPException(status_code=400, detail="At least one prescription line is required")

    if customer_id:
        party = (
            await db.execute(
                select(m.Party).where(
                    m.Party.id == customer_id,
                    m.Party.tenant_id == tenant_id,
                    m.Party.kind == "customer",
                )
            )
        ).scalar_one_or_none()
        if not party:
            raise HTTPException(status_code=404, detail="Customer not found")

    if sale_id:
        invoice = (
            await db.execute(
                select(m.SalesInvoice).where(
                    m.SalesInvoice.id == sale_id,
                    m.SalesInvoice.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Sale not found")

    cleaned_name = optional_honest_narrative(
        prescriber_name, label="prescriber name", max_length=150
    )
    cleaned_notes = optional_honest_narrative(notes, label="prescription notes")

    rx_number = await allocate_rx_number(db, tenant_id)
    header = m.Prescription(
        tenant_id=tenant_id,
        rx_number=rx_number,
        customer_id=customer_id,
        sale_id=sale_id,
        prescriber_name=cleaned_name,
        notes=cleaned_notes,
        status="received",
        created_by=created_by,
    )
    db.add(header)
    await db.flush()

    for raw in items:
        product_id = str(raw.get("product_id") or "").strip()
        from app.catalog import get_product

        product = await get_product(db, tenant_id, product_id)
        variant_id = raw.get("variant_id")
        if variant_id:
            variant = (
                await db.execute(
                    select(m.ProductVariant).where(
                        m.ProductVariant.id == variant_id,
                        m.ProductVariant.tenant_id == tenant_id,
                        m.ProductVariant.product_id == product.id,
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                raise HTTPException(status_code=404, detail="Variant not found")
        qty = money_json(raw.get("quantity") or 0)
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Line quantity must be greater than zero")
        dosage = optional_honest_narrative(
            raw.get("dosage_text"), label="dosage instructions"
        ) or getattr(product, "dosage_instructions", None)
        line_notes = optional_honest_narrative(raw.get("notes"), label="line notes")
        db.add(
            m.PrescriptionItem(
                tenant_id=tenant_id,
                prescription_id=header.id,
                product_id=product.id,
                variant_id=variant_id,
                quantity=qty,
                qty_dispensed=0,
                dosage_text=dosage,
                notes=line_notes,
            )
        )
    await db.flush()
    return header


async def transition_prescription(
    db: AsyncSession,
    *,
    tenant_id: str,
    prescription_id: str,
    status: str,
    sale_id: str | None = None,
    created_by: str | None = None,
) -> m.Prescription:
    row = (
        await db.execute(
            select(m.Prescription).where(
                m.Prescription.id == prescription_id,
                m.Prescription.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Prescription not found")
    target = canonicalize_rx_status(status)
    if target not in RX_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of: {', '.join(sorted(RX_STATUSES))}",
        )
    current = canonicalize_rx_status(row.status)
    if current == target:
        return row
    allowed = RX_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move a {current} prescription to {target}",
        )
    if target == "dispensed" and sale_id:
        invoice = (
            await db.execute(
                select(m.SalesInvoice).where(
                    m.SalesInvoice.id == sale_id,
                    m.SalesInvoice.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Sale not found")
        row.sale_id = invoice.id
    now = datetime.utcnow()
    if target == "approved":
        row.approved_by = row.approved_by or created_by
        row.approved_at = row.approved_at or now
    if target == "dispensed":
        row.dispensed_at = row.dispensed_at or now
    row.status = target
    await db.flush()
    return row


async def void_prescription(
    db: AsyncSession, *, tenant_id: str, prescription_id: str
) -> m.Prescription:
    return await transition_prescription(
        db, tenant_id=tenant_id, prescription_id=prescription_id, status="cancelled"
    )


async def list_rx_products(db: AsyncSession, *, tenant_id: str) -> list[m.Product]:
    from app import schema_compat as schema_compat_svc

    cols = await schema_compat_svc.table_column_names(db, "products")
    if "rx_only" not in cols:
        return []
    return await schema_compat_svc.list_mapped(
        db,
        m.Product,
        tenant_id=tenant_id,
        extra="rx_only = :rx",
        extra_params={"rx": True},
        order_by="name",
    )


async def open_hold_batch_ids(
    db: AsyncSession, tenant_id: str, batch_ids: list[str] | None = None
) -> set[str]:
    if not hasattr(m, "BatchHold"):
        return set()
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "batch_holds"):
        return set()
    stmt = select(m.BatchHold.batch_id).where(
        m.BatchHold.tenant_id == tenant_id,
        m.BatchHold.status == "open",
    )
    if batch_ids is not None:
        if not batch_ids:
            return set()
        stmt = stmt.where(m.BatchHold.batch_id.in_(list(batch_ids)))
    return {row[0] for row in (await db.execute(stmt)).all()}


async def list_holds(
    db: AsyncSession, *, tenant_id: str, status: str | None = "open"
) -> list[dict]:
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "batch_holds"):
        return []
    stmt = select(m.BatchHold).where(m.BatchHold.tenant_id == tenant_id)
    if status:
        key = status.strip().lower()
        if key not in {"open", "released"}:
            raise HTTPException(status_code=422, detail="status must be open or released")
        stmt = stmt.where(m.BatchHold.status == key)
    stmt = stmt.order_by(m.BatchHold.created_at.desc())
    rows = list((await db.execute(stmt)).scalars().all())
    batch_ids = [r.batch_id for r in rows]
    batches: dict[str, m.ProductBatch] = {}
    if batch_ids:
        found = (
            await db.execute(
                select(m.ProductBatch).where(
                    m.ProductBatch.tenant_id == tenant_id,
                    m.ProductBatch.id.in_(batch_ids),
                )
            )
        ).scalars().all()
        batches = {b.id: b for b in found}
    names = await _product_names(db, tenant_id, {b.product_id for b in batches.values()})
    out = []
    for row in rows:
        batch = batches.get(row.batch_id)
        out.append(
            serialize_hold(
                row,
                batch_number=batch.batch_number if batch else None,
                product_id=batch.product_id if batch else None,
                product_name=names.get(batch.product_id) if batch else None,
                expiry_date=batch.expiry_date if batch else None,
            )
        )
    return out


async def create_hold(
    db: AsyncSession,
    *,
    tenant_id: str,
    created_by: str | None,
    batch_id: str,
    hold_type: str,
    reason: str | None,
) -> m.BatchHold:
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "batch_holds"):
        raise HTTPException(status_code=409, detail="Lot holds require migration 0131")
    kind = (hold_type or "").strip().lower()
    if kind not in HOLD_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"hold_type must be one of: {', '.join(sorted(HOLD_TYPES))}",
        )
    batch = (
        await db.execute(
            select(m.ProductBatch).where(
                m.ProductBatch.id == batch_id,
                m.ProductBatch.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    existing = (
        await db.execute(
            select(m.BatchHold).where(
                m.BatchHold.tenant_id == tenant_id,
                m.BatchHold.batch_id == batch.id,
            )
        )
    ).scalar_one_or_none()
    cleaned = require_honest_narrative(reason, label="hold reason", max_length=500)
    now = datetime.utcnow()
    if existing:
        existing.hold_type = kind
        existing.status = "open"
        existing.reason = cleaned
        existing.created_by = created_by
        existing.created_at = now
        existing.released_at = None
        await db.flush()
        return existing
    row = m.BatchHold(
        tenant_id=tenant_id,
        batch_id=batch.id,
        hold_type=kind,
        status="open",
        reason=cleaned,
        created_by=created_by,
        created_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def release_hold(
    db: AsyncSession, *, tenant_id: str, hold_id: str
) -> m.BatchHold:
    row = (
        await db.execute(
            select(m.BatchHold).where(
                m.BatchHold.id == hold_id,
                m.BatchHold.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Hold not found")
    if row.status != "released":
        row.status = "released"
        row.released_at = datetime.utcnow()
        await db.flush()
    return row


async def _load_prescription(
    db: AsyncSession, *, tenant_id: str, prescription_id: str
) -> m.Prescription:
    row = (
        await db.execute(
            select(m.Prescription).where(
                m.Prescription.id == prescription_id,
                m.Prescription.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return row


async def _items_for(db: AsyncSession, tenant_id: str, prescription_id: str) -> list[m.PrescriptionItem]:
    return list(
        (
            await db.execute(
                select(m.PrescriptionItem)
                .where(
                    m.PrescriptionItem.tenant_id == tenant_id,
                    m.PrescriptionItem.prescription_id == prescription_id,
                )
                .order_by(m.PrescriptionItem.id.asc())
            )
        ).scalars().all()
    )


def _refresh_fill_status(row: m.Prescription, items: list[m.PrescriptionItem]) -> None:
    remaining = 0.0
    dispensed_any = False
    for item in items:
        qty = money_json(item.quantity or 0)
        done = money_json(getattr(item, "qty_dispensed", 0) or 0)
        remaining += max(qty - done, 0)
        if done > 1e-9:
            dispensed_any = True
    if remaining <= 1e-9:
        row.status = "dispensed"
        row.dispensed_at = row.dispensed_at or datetime.utcnow()
    elif dispensed_any:
        row.status = "partially_dispensed"


async def dispense_lines(
    db: AsyncSession,
    *,
    tenant_id: str,
    prescription_id: str,
    items: list[dict],
    user_id: str | None,
    sale_id: str | None = None,
    skip_stock: bool = False,
) -> m.Prescription:
    """Partial or full fill. Stock moves here unless POS already deducted (skip_stock)."""
    row = await _load_prescription(db, tenant_id=tenant_id, prescription_id=prescription_id)
    current = canonicalize_rx_status(row.status)
    if current not in RX_DISPENSE_OK:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RX_NOT_APPROVED",
                "message": "Pharmacist must approve the prescription before dispensing",
                "status": current,
            },
        )
    if not items:
        raise HTTPException(status_code=400, detail="At least one dispense line is required")
    lines = await _items_for(db, tenant_id, row.id)
    by_product: dict[tuple[str, str | None], m.PrescriptionItem] = {
        (i.product_id, i.variant_id): i for i in lines
    }
    from app.catalog import stock_out_with_batch

    for raw in items:
        product_id = str(raw.get("product_id") or "").strip()
        variant_id = raw.get("variant_id")
        take = money_json(raw.get("quantity") or 0)
        if take <= 0:
            raise HTTPException(status_code=400, detail="Dispense quantity must be greater than zero")
        line = by_product.get((product_id, variant_id)) or by_product.get((product_id, None))
        if not line:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "RX_LINE_MISMATCH",
                    "message": "Product is not on this prescription",
                    "product_id": product_id,
                },
            )
        already = money_json(getattr(line, "qty_dispensed", 0) or 0)
        remaining = money_json(max(money_json(line.quantity or 0) - already, 0))
        if take - remaining > 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "RX_QTY_EXCEEDED",
                    "message": "Cannot dispense more than remaining prescribed quantity",
                    "remaining": remaining,
                    "requested": take,
                },
            )
        if not skip_stock:
            await stock_out_with_batch(
                db,
                tenant_id=tenant_id,
                user_id=user_id or "",
                product_id=line.product_id,
                quantity=take,
                variant_id=line.variant_id,
                notes=f"Rx {row.rx_number}",
                reference_type="prescription",
                reference_id=row.id,
            )
        line.qty_dispensed = money_json(already + take)
    if sale_id:
        row.sale_id = sale_id
    _refresh_fill_status(row, lines)
    await db.flush()
    return row


async def assert_pos_prescription(
    db: AsyncSession,
    *,
    tenant_id: str,
    industry: str | None,
    prescription_id: str | None,
    items: list[dict],
) -> None:
    """Pharmacy Rx-only lines need an approved prescription covering remaining qty."""
    from app.packages import canonicalize_industry
    from app.catalog import get_product

    if canonicalize_industry(industry) != "pharmacy":
        return
    rx_lines: list[dict] = []
    for item in items:
        product = await get_product(db, tenant_id, str(item.get("product_id") or ""))
        if bool(getattr(product, "rx_only", False)):
            rx_lines.append(item)
    if not rx_lines:
        return
    if not prescription_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RX_REQUIRED",
                "message": "Rx-only products require an approved prescription on this sale",
            },
        )
    row = await _load_prescription(db, tenant_id=tenant_id, prescription_id=prescription_id)
    current = canonicalize_rx_status(row.status)
    if current not in RX_DISPENSE_OK:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RX_NOT_APPROVED",
                "message": "Pharmacist must approve the prescription before POS dispense",
                "status": current,
            },
        )
    lines = await _items_for(db, tenant_id, row.id)
    remaining_by: dict[str, float] = {}
    for line in lines:
        leftover = money_json(line.quantity or 0) - money_json(getattr(line, "qty_dispensed", 0) or 0)
        remaining_by[line.product_id] = remaining_by.get(line.product_id, 0) + max(leftover, 0)
    for item in rx_lines:
        pid = str(item.get("product_id") or "")
        qty = money_json(item.get("quantity") or 0)
        have = remaining_by.get(pid, 0)
        if qty - have > 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "RX_QTY_EXCEEDED",
                    "message": "Sale quantity exceeds remaining prescribed quantity",
                    "product_id": pid,
                    "remaining": money_json(have),
                    "requested": qty,
                },
            )
        remaining_by[pid] = have - qty


async def apply_pos_dispense(
    db: AsyncSession,
    *,
    tenant_id: str,
    industry: str | None,
    prescription_id: str | None,
    sale_id: str,
    items: list[dict],
    user_id: str | None,
) -> None:
    from app.packages import canonicalize_industry
    from app.catalog import get_product

    if canonicalize_industry(industry) != "pharmacy" or not prescription_id:
        return
    dispense_items = []
    for item in items:
        product = await get_product(db, tenant_id, str(item.get("product_id") or ""))
        if bool(getattr(product, "rx_only", False)):
            dispense_items.append(
                {
                    "product_id": product.id,
                    "variant_id": item.get("variant_id"),
                    "quantity": item.get("quantity"),
                }
            )
    if not dispense_items:
        return
    await dispense_lines(
        db,
        tenant_id=tenant_id,
        prescription_id=prescription_id,
        items=dispense_items,
        user_id=user_id,
        sale_id=sale_id,
        skip_stock=True,
    )


async def add_attachment(
    db: AsyncSession,
    *,
    tenant_id: str,
    prescription_id: str,
    storage_key: str,
    content_type: str | None,
    original_filename: str | None,
    created_by: str | None,
) -> m.PrescriptionAttachment:
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "prescription_attachments"):
        raise HTTPException(status_code=409, detail="Prescription attachments require migration 0131")
    await _load_prescription(db, tenant_id=tenant_id, prescription_id=prescription_id)
    row = m.PrescriptionAttachment(
        tenant_id=tenant_id,
        prescription_id=prescription_id,
        storage_key=storage_key,
        content_type=content_type,
        original_filename=original_filename,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row


async def get_attachment(
    db: AsyncSession, *, tenant_id: str, prescription_id: str, attachment_id: str
) -> m.PrescriptionAttachment:
    await _load_prescription(db, tenant_id=tenant_id, prescription_id=prescription_id)
    row = (
        await db.execute(
            select(m.PrescriptionAttachment).where(
                m.PrescriptionAttachment.id == attachment_id,
                m.PrescriptionAttachment.tenant_id == tenant_id,
                m.PrescriptionAttachment.prescription_id == prescription_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return row


async def rx_activity(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Prescription counts and fills from the Rx ledger — not a clinic report."""
    from app import schema_compat as schema_compat_svc

    if not await schema_compat_svc.table_column_names(db, "prescriptions"):
        return {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "counts": {key: 0 for key in RX_STATUSES} | {"open": 0, "total": 0},
            "qty_prescribed": 0,
            "qty_dispensed": 0,
            "prescriptions": [],
        }
    stmt = select(m.Prescription).where(m.Prescription.tenant_id == tenant_id)
    if from_date:
        stmt = stmt.where(m.Prescription.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.Prescription.created_at < to_date)
    stmt = stmt.order_by(m.Prescription.created_at.desc()).limit(500)
    rows = list((await db.execute(stmt)).scalars().all())
    counts = {key: 0 for key in RX_STATUSES}
    out = []
    qty_prescribed = 0.0
    qty_dispensed = 0.0
    for row in rows:
        data = await _hydrate(db, tenant_id, row)
        status = canonicalize_rx_status(row.status)
        counts[status] = counts.get(status, 0) + 1
        for item in data.get("items") or []:
            qty_prescribed += money_json(item.get("quantity") or 0)
            qty_dispensed += money_json(item.get("qty_dispensed") or 0)
        out.append(
            {
                "id": data["id"],
                "rx_number": data["rx_number"],
                "status": data["status"],
                "customer_name": data.get("customer_name"),
                "sale_number": data.get("sale_number"),
                "created_at": data.get("created_at"),
                "dispensed_at": data.get("dispensed_at"),
                "item_count": len(data.get("items") or []),
                "qty_remaining": money_json(
                    sum(money_json(i.get("qty_remaining") or 0) for i in (data.get("items") or []))
                ),
            }
        )
    counts["open"] = sum(counts[k] for k in RX_OPEN_QUEUE)
    counts["total"] = len(rows)
    return {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "counts": counts,
        "qty_prescribed": money_json(qty_prescribed),
        "qty_dispensed": money_json(qty_dispensed),
        "prescriptions": out,
    }
