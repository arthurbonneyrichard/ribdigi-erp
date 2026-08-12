"""Purchase request (PR) workflow: draft → pending → approved/rejected → converted PO."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import purchasing as purchasing_svc
from app.doc_numbers import next_purchase_request_number

PR_EDITABLE = frozenset({"draft"})
PR_APPROVABLE = frozenset({"pending"})
PR_CONVERTIBLE = frozenset({"approved"})
APPROVER_ROLES = frozenset({"store_manager", "company_admin", "super_admin"})


async def get_request(db: AsyncSession, tenant_id: str, request_id: str) -> m.PurchaseRequest:
    row = (
        await db.execute(
            select(m.PurchaseRequest).where(
                m.PurchaseRequest.id == request_id,
                m.PurchaseRequest.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return row


async def list_items(
    db: AsyncSession, tenant_id: str, request_id: str
) -> list[m.PurchaseRequestItem]:
    return list(
        (
            await db.execute(
                select(m.PurchaseRequestItem).where(
                    m.PurchaseRequestItem.tenant_id == tenant_id,
                    m.PurchaseRequestItem.purchase_request_id == request_id,
                )
            )
        )
        .scalars()
        .all()
    )


async def serialize_request(db: AsyncSession, row: m.PurchaseRequest) -> dict:
    items = await list_items(db, row.tenant_id, row.id)
    return {
        "id": row.id,
        "request_number": row.request_number,
        "status": row.status,
        "preferred_supplier_id": row.preferred_supplier_id,
        "warehouse_id": row.warehouse_id,
        "required_date": row.required_date,
        "department": row.department,
        "notes": row.notes,
        "created_by": row.created_by,
        "approved_by": row.approved_by,
        "rejected_by": row.rejected_by,
        "rejection_reason": row.rejection_reason,
        "converted_po_id": row.converted_po_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "notes": i.notes,
            }
            for i in items
        ],
    }


async def create_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    items: list[dict],
    preferred_supplier_id: str | None = None,
    warehouse_id: str | None = None,
    required_date: datetime | None = None,
    department: str | None = None,
    notes: str | None = None,
) -> m.PurchaseRequest:
    if not items:
        raise HTTPException(status_code=400, detail="Purchase request requires at least one line")
    if preferred_supplier_id:
        await purchasing_svc.get_supplier(db, tenant_id, preferred_supplier_id)
    if warehouse_id:
        wh = (
            await db.execute(
                select(m.Warehouse).where(
                    m.Warehouse.id == warehouse_id,
                    m.Warehouse.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not wh:
            raise HTTPException(status_code=404, detail="Warehouse not found")

    prepared: list[dict] = []
    for item in items:
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == item["product_id"],
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item['product_id']}")
        qty = float(item.get("quantity") or 0)
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Line quantity must be > 0")
        variant_id = item.get("variant_id")
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
                raise HTTPException(status_code=404, detail=f"Variant not found: {variant_id}")
        prepared.append(
            {
                "product_id": product.id,
                "variant_id": variant_id,
                "quantity": qty,
                "notes": (item.get("notes") or None),
            }
        )

    number = await next_purchase_request_number(db, tenant_id)
    row = m.PurchaseRequest(
        tenant_id=tenant_id,
        request_number=number,
        status="draft",
        preferred_supplier_id=preferred_supplier_id,
        warehouse_id=warehouse_id,
        required_date=required_date,
        department=((department or "").strip()[:120] or None),
        notes=notes,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    for item in prepared:
        db.add(
            m.PurchaseRequestItem(
                tenant_id=tenant_id,
                purchase_request_id=row.id,
                product_id=item["product_id"],
                variant_id=item.get("variant_id"),
                quantity=item["quantity"],
                notes=item.get("notes"),
            )
        )
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_created",
            entity="purchase_request",
            entity_id=row.id,
            details={"request_number": row.request_number},
        )
    )
    return row


async def submit_request(
    db: AsyncSession, *, tenant_id: str, user_id: str, request_id: str
) -> m.PurchaseRequest:
    row = await get_request(db, tenant_id, request_id)
    if row.status not in PR_EDITABLE:
        raise HTTPException(status_code=409, detail=f"Cannot submit PR in status {row.status}")
    items = await list_items(db, tenant_id, row.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot submit empty purchase request")
    row.status = "pending"
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_submitted",
            entity="purchase_request",
            entity_id=row.id,
            details={"request_number": row.request_number},
        )
    )
    return row


async def approve_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    request_id: str,
    actor_role: str | None = None,
) -> m.PurchaseRequest:
    row = await get_request(db, tenant_id, request_id)
    if row.status not in PR_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot approve PR in status {row.status}")
    role = (actor_role or "").strip()
    if role not in APPROVER_ROLES and role != "super_admin":
        # company_admin / store_manager enforced primarily via RBAC; keep defense in depth
        if role not in {"company_admin", "store_manager", "super_admin"}:
            raise HTTPException(status_code=403, detail="Role cannot approve purchase requests")
    if row.created_by and row.created_by == user_id and role != "super_admin":
        raise HTTPException(status_code=403, detail="Cannot approve your own purchase request")
    row.status = "approved"
    row.approved_by = user_id
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_approved",
            entity="purchase_request",
            entity_id=row.id,
            details={"request_number": row.request_number},
        )
    )
    return row


async def reject_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    request_id: str,
    reason: str | None = None,
    actor_role: str | None = None,
) -> m.PurchaseRequest:
    row = await get_request(db, tenant_id, request_id)
    if row.status not in PR_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot reject PR in status {row.status}")
    role = (actor_role or "").strip()
    if row.created_by and row.created_by == user_id and role != "super_admin":
        raise HTTPException(status_code=403, detail="Cannot reject your own purchase request")
    row.status = "rejected"
    row.rejected_by = user_id
    row.rejection_reason = (reason or "").strip() or None
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_rejected",
            entity="purchase_request",
            entity_id=row.id,
            details={"request_number": row.request_number, "reason": row.rejection_reason},
        )
    )
    return row


async def convert_to_po(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    request_id: str,
    supplier_id: str | None = None,
) -> tuple[m.PurchaseRequest, m.PurchaseOrder]:
    row = await get_request(db, tenant_id, request_id)
    if row.status not in PR_CONVERTIBLE:
        raise HTTPException(status_code=409, detail=f"Cannot convert PR in status {row.status}")
    supplier = supplier_id or row.preferred_supplier_id
    if not supplier:
        raise HTTPException(
            status_code=400,
            detail="Supplier is required to convert this purchase request",
        )
    items = await list_items(db, tenant_id, row.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot convert empty purchase request")

    po_items: list[dict] = []
    for item in items:
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == item.product_id,
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        unit_price = float(product.cost_price or 0) if product else 0.0
        po_items.append(
            {
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "unit_price": unit_price,
                "tax_rate": 0,
            }
        )

    notes = row.notes or ""
    pr_note = f"Converted from {row.request_number}"
    po_notes = f"{pr_note}. {notes}".strip() if notes else pr_note
    po = await purchasing_svc.create_purchase_order(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        supplier_id=supplier,
        warehouse_id=row.warehouse_id,
        notes=po_notes,
        items=po_items,
    )
    row.status = "converted"
    row.converted_po_id = po.id
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_converted",
            entity="purchase_request",
            entity_id=row.id,
            details={
                "request_number": row.request_number,
                "po_id": po.id,
                "po_number": po.po_number,
            },
        )
    )
    return row, po
