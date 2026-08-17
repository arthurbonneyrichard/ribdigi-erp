"""Purchase request (PR) workflow: draft → pending → approved/rejected → converted PO.

Supports configurable N-level role-chain approval (BR-6.2), mirroring expenses
but without amount thresholds — every submitted PR walks all configured levels.
"""

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
# Manage list statuses (full PR lifecycle).
PR_MANAGE_STATUSES = frozenset(
    {"draft", "pending", "approved", "rejected", "converted"}
)
MAX_APPROVAL_LEVELS = 5


def default_approval_levels() -> list[dict]:
    """BR-6.2 default: Store Manager → Company Admin."""
    return [
        {
            "step": 1,
            "roles": ["store_manager"],
            "label": "Store Manager",
        },
        {
            "step": 2,
            "roles": ["company_admin", "super_admin"],
            "label": "Company Admin",
        },
    ]


def normalize_approval_matrix(raw: dict | list | None) -> list[dict]:
    """Validate/normalize PR role-chain levels (no amount thresholds)."""
    from app.rbac import VALID_ROLES

    if raw is None:
        return default_approval_levels()
    if isinstance(raw, dict):
        levels_in = raw.get("levels")
    else:
        levels_in = raw
    if not isinstance(levels_in, list) or not levels_in:
        raise HTTPException(status_code=400, detail="approval matrix levels must be a non-empty list")
    if len(levels_in) > MAX_APPROVAL_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"at most {MAX_APPROVAL_LEVELS} approval levels allowed",
        )

    levels: list[dict] = []
    for i, item in enumerate(levels_in):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"level {i + 1} must be an object")
        roles_raw = item.get("roles") or []
        if not isinstance(roles_raw, list) or not roles_raw:
            raise HTTPException(status_code=400, detail=f"level {i + 1} roles must be a non-empty list")
        roles: list[str] = []
        for r in roles_raw:
            role = str(r or "").strip()
            if not role:
                continue
            if role not in VALID_ROLES:
                raise HTTPException(status_code=400, detail=f"unknown role '{role}' in level {i + 1}")
            if role not in roles:
                roles.append(role)
        if not roles:
            raise HTTPException(status_code=400, detail=f"level {i + 1} roles must be a non-empty list")
        label = str(item.get("label") or f"Level {i + 1}").strip() or f"Level {i + 1}"
        levels.append({"step": i + 1, "roles": roles, "label": label})
    return levels


def matrix_payload(levels: list[dict]) -> dict:
    return {"levels": levels}


def roles_for_step(levels: list[dict], step: int) -> list[str]:
    for lvl in levels:
        if int(lvl["step"]) == int(step):
            return list(lvl["roles"])
    return []


def assert_actor_may_act(*, levels: list[dict], step: int, actor_role: str | None) -> None:
    role = (actor_role or "").strip()
    if role == "super_admin":
        return
    allowed = roles_for_step(levels, step)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"No approval level configured for step {step}")
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Level-{step} approval requires one of: {', '.join(allowed)}",
        )


def resolve_tenant_levels(tenant: m.Tenant) -> list[dict]:
    raw = getattr(tenant, "purchase_approval_matrix", None)
    if raw:
        try:
            return normalize_approval_matrix(raw)
        except HTTPException:
            pass
    return default_approval_levels()


def settings_from_levels(levels: list[dict]) -> dict:
    return {
        "levels": levels,
        "max_levels": MAX_APPROVAL_LEVELS,
        "steps_required": len(levels),
    }


async def get_approval_settings(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return settings_from_levels(resolve_tenant_levels(tenant))


async def update_approval_settings(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    levels: list[dict],
) -> dict:
    normalized = normalize_approval_matrix({"levels": levels})
    tenant.purchase_approval_matrix = matrix_payload(normalized)
    await db.flush()
    return settings_from_levels(normalized)


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


async def list_approval_actions(
    db: AsyncSession, tenant_id: str, request_id: str
) -> list[m.PurchaseRequestApprovalAction]:
    return list(
        (
            await db.execute(
                select(m.PurchaseRequestApprovalAction)
                .where(
                    m.PurchaseRequestApprovalAction.tenant_id == tenant_id,
                    m.PurchaseRequestApprovalAction.purchase_request_id == request_id,
                )
                .order_by(m.PurchaseRequestApprovalAction.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


def serialize_approval_action(row: m.PurchaseRequestApprovalAction) -> dict:
    return {
        "id": row.id,
        "purchase_request_id": row.purchase_request_id,
        "step": int(row.step),
        "action": row.action,
        "actor_id": row.actor_id,
        "comment": row.comment,
        "created_at": row.created_at,
    }


async def _record_action(
    db: AsyncSession,
    *,
    tenant_id: str,
    request_id: str,
    step: int,
    action: str,
    actor_id: str | None,
    comment: str | None = None,
) -> m.PurchaseRequestApprovalAction:
    row = m.PurchaseRequestApprovalAction(
        tenant_id=tenant_id,
        purchase_request_id=request_id,
        step=step,
        action=action,
        actor_id=actor_id,
        comment=comment,
    )
    db.add(row)
    await db.flush()
    return row


async def serialize_request(db: AsyncSession, row: m.PurchaseRequest) -> dict:
    items = await list_items(db, row.tenant_id, row.id)
    actions = await list_approval_actions(db, row.tenant_id, row.id)
    step = int(getattr(row, "approval_step", 1) or 1)
    required = int(getattr(row, "approval_steps_required", 1) or 1)
    data = {
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
        "approval_step": step,
        "approval_steps_required": required,
        "awaiting_level": step if row.status == "pending" else None,
        "converted_po_id": row.converted_po_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "approval_actions": [serialize_approval_action(a) for a in actions],
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
    if row.status == "pending":
        settings = await get_approval_settings(db, row.tenant_id)
        data["awaiting_roles"] = roles_for_step(settings["levels"], step)
    return data


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
        await purchasing_svc.require_active_supplier(db, tenant_id, preferred_supplier_id)
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
        if not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product is inactive: {product.sku}")
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
        approval_step=0,
        approval_steps_required=0,
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
    settings = await get_approval_settings(db, tenant_id)
    steps = len(settings["levels"])
    if steps < 1:
        raise HTTPException(status_code=400, detail="Purchase approval matrix has no levels")
    row.status = "pending"
    row.approval_step = 1
    row.approval_steps_required = steps
    row.approved_by = None
    row.rejected_by = None
    row.rejection_reason = None
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_submitted",
            entity="purchase_request",
            entity_id=row.id,
            details={
                "request_number": row.request_number,
                "approval_steps_required": steps,
            },
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
    comment: str | None = None,
) -> m.PurchaseRequest:
    row = await get_request(db, tenant_id, request_id)
    if row.status not in PR_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot approve PR in status {row.status}")
    role = (actor_role or "").strip()
    if row.created_by and row.created_by == user_id and role != "super_admin":
        raise HTTPException(status_code=403, detail="Cannot approve your own purchase request")

    step = int(row.approval_step or 1)
    required = int(row.approval_steps_required or 1)
    settings = await get_approval_settings(db, tenant_id)
    assert_actor_may_act(levels=settings["levels"], step=step, actor_role=actor_role)

    prior = await list_approval_actions(db, tenant_id, row.id)
    if any(a.action == "approve" and a.actor_id == user_id for a in prior):
        raise HTTPException(
            status_code=403,
            detail="You already approved an earlier step on this purchase request",
        )

    await _record_action(
        db,
        tenant_id=tenant_id,
        request_id=row.id,
        step=step,
        action="approve",
        actor_id=user_id,
        comment=comment,
    )

    now = datetime.utcnow()
    if step < required:
        row.approval_step = step + 1
        row.updated_at = now
        db.add(
            m.AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action="pr_step_approved",
                entity="purchase_request",
                entity_id=row.id,
                details={
                    "request_number": row.request_number,
                    "step": step,
                    "next_step": step + 1,
                },
            )
        )
        from app.notifications import create_notification

        await create_notification(
            db,
            tenant_id=tenant_id,
            category="system",
            title="Purchase request needs next-level approval",
            message=(
                f"PR {row.request_number} passed level {step} "
                f"and awaits level {step + 1} approval."
            ),
            entity_type="purchase_request",
            entity_id=row.id,
        )
        await db.flush()
        return row

    row.status = "approved"
    row.approved_by = user_id
    row.approval_step = required
    row.updated_at = now
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_approved",
            entity="purchase_request",
            entity_id=row.id,
            details={"request_number": row.request_number, "steps": required},
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

    step = int(row.approval_step or 1)
    settings = await get_approval_settings(db, tenant_id)
    assert_actor_may_act(levels=settings["levels"], step=step, actor_role=actor_role)

    reason_s = (reason or "").strip()
    if not reason_s:
        raise HTTPException(status_code=400, detail="rejection reason is required")
    await _record_action(
        db,
        tenant_id=tenant_id,
        request_id=row.id,
        step=step,
        action="reject",
        actor_id=user_id,
        comment=reason_s,
    )
    row.status = "rejected"
    row.rejected_by = user_id
    row.rejection_reason = reason_s
    row.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_rejected",
            entity="purchase_request",
            entity_id=row.id,
            details={
                "request_number": row.request_number,
                "reason": reason_s,
                "step": step,
            },
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
