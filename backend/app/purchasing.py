"""Purchase order and GRN business logic."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import catalog as catalog_svc
from app.inventory import apply_stock_change
from app.tax import compute_line_total, compute_tax_amounts
from app.credit import default_due_date

PO_EDITABLE = {"draft"}
PO_AMENDABLE = {"draft", "sent", "partially_received"}
PO_RECEIVABLE = {"sent", "partially_received"}
PR_EDITABLE = {"draft"}
PR_SUBMITTABLE = {"draft"}
PR_APPROVABLE = {"pending"}
PR_CONVERTIBLE = {"approved"}
PR_CANCELLABLE = {"draft", "pending", "approved"}
PURCHASE_RETURN_REASONS = frozenset({"damaged", "wrong_item", "expiry", "quality", "other"})
_UNSET = object()


def _calc_po_line_amounts(
    quantity: float,
    unit_price: float,
    tax_rate: float = 0,
    discount: float = 0,
) -> tuple[float, float, float, float]:
    """Return (line_sub, line_tax, line_total, discount) with tax on net after discount."""
    qty = float(quantity or 0)
    price = float(unit_price or 0)
    rate = float(tax_rate or 0)
    disc = round(float(discount or 0), 2)
    if disc < 0:
        raise HTTPException(status_code=400, detail="Line discount must be >= 0")
    gross_before = round(qty * price, 2)
    if disc > gross_before + 1e-9:
        raise HTTPException(status_code=400, detail="Line discount exceeds line amount")
    net, tax, gross = compute_tax_amounts(gross_before - disc, rate, "exclusive")
    return float(net), float(tax), float(gross), disc


def _calc_partial_po_line_amounts(
    quantity: float,
    unit_price: float,
    tax_rate: float,
    line_discount: float,
    ordered_qty: float,
) -> tuple[float, float, float, float]:
    """Scale absolute PO line discount by qty/ordered for partial GRN / PI lines (Stage 11 C1)."""
    ordered = float(ordered_qty or 0)
    qty = float(quantity or 0)
    disc = float(line_discount or 0)
    scaled = round(disc * (qty / ordered), 2) if ordered > 0 and disc > 0 else 0.0
    return _calc_po_line_amounts(qty, unit_price, tax_rate, scaled)


async def po_received_accepted_value(
    db: AsyncSession, tenant_id: str, purchase_order_id: str
) -> float:
    """Economic AP value of accepted GRN qty on a PO (discount + tax aware)."""
    items = await list_po_items(db, tenant_id, purchase_order_id)
    total = 0.0
    for item in items:
        received = float(item.received_qty or 0)
        if received <= 0:
            continue
        _, _, line_total, _ = _calc_partial_po_line_amounts(
            received,
            float(item.unit_price or 0),
            float(item.tax_rate or 0),
            float(item.discount or 0),
            float(item.quantity or 0),
        )
        total += line_total
    return round(total, 2)


PURCHASE_INVOICE_OPEN = frozenset({"unpaid", "partial", "overdue"})

# BR-6.2: Inventory Officer creates → Store Manager → (high value) Company Admin
DEFAULT_PR_L1_MIN = 0.01
DEFAULT_PR_L2_MIN = 5000.0
DEFAULT_PR_L1_ROLES = ("store_manager", "company_admin", "super_admin")
DEFAULT_PR_L2_ROLES = ("company_admin", "super_admin")


def default_pr_approval_levels(
    *,
    l1_min: float = DEFAULT_PR_L1_MIN,
    l2_min: float = DEFAULT_PR_L2_MIN,
) -> list[dict]:
    from app.expenses import normalize_approval_matrix

    return normalize_approval_matrix(
        {
            "levels": [
                {
                    "min_amount": l1_min,
                    "roles": list(DEFAULT_PR_L1_ROLES),
                    "label": "Store Manager",
                },
                {
                    "min_amount": max(float(l2_min), float(l1_min) + 0.01),
                    "roles": list(DEFAULT_PR_L2_ROLES),
                    "label": "Company Admin",
                },
            ]
        }
    )


def resolve_pr_approval_levels(tenant: m.Tenant) -> list[dict]:
    from app.expenses import normalize_approval_matrix

    raw = getattr(tenant, "purchase_request_approval_matrix", None)
    if raw:
        try:
            return normalize_approval_matrix(raw)
        except HTTPException:
            pass
    return default_pr_approval_levels()


async def get_pr_approval_settings(db: AsyncSession, tenant_id: str) -> dict:
    from app.expenses import MAX_APPROVAL_LEVELS

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    levels = resolve_pr_approval_levels(tenant)
    return {
        "levels": levels,
        "max_levels": MAX_APPROVAL_LEVELS,
        "l1_threshold": float(levels[0]["min_amount"]) if levels else DEFAULT_PR_L1_MIN,
        "l2_threshold": float(levels[1]["min_amount"]) if len(levels) > 1 else DEFAULT_PR_L2_MIN,
    }


async def update_pr_approval_settings(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    levels: list[dict],
) -> dict:
    from app.expenses import matrix_payload, normalize_approval_matrix

    normalized = normalize_approval_matrix({"levels": levels})
    tenant.purchase_request_approval_matrix = matrix_payload(normalized)
    await db.flush()
    return await get_pr_approval_settings(db, tenant.id)


def estimate_pr_total(items: list[m.PurchaseRequestItem] | list[dict]) -> float:
    total = 0.0
    for item in items:
        if isinstance(item, dict):
            qty = float(item.get("quantity") or 0)
            price = float(item.get("unit_price") or 0)
            tax_rate = float(item.get("tax_rate") or 0)
        else:
            qty = float(item.quantity or 0)
            price = float(item.unit_price or 0)
            tax_rate = float(item.tax_rate or 0)
        subtotal, tax, line_total = compute_line_total(qty, price, tax_rate)
        total += float(line_total)
    return round(total, 2)


async def list_pr_approval_actions(
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


def serialize_pr_approval_action(row: m.PurchaseRequestApprovalAction) -> dict:
    return {
        "id": row.id,
        "purchase_request_id": row.purchase_request_id,
        "step": int(row.step),
        "action": row.action,
        "actor_id": row.actor_id,
        "comment": row.comment,
        "created_at": row.created_at,
    }


async def _record_pr_action(
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
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


def purchase_invoice_status(total: float, paid: float, due_date: datetime | None = None) -> str:
    if paid + 1e-9 >= total:
        return "paid"
    base = "partial" if paid > 0 else "unpaid"
    if due_date and datetime.utcnow().date() > due_date.date():
        return "overdue"
    return base


def derive_po_status(items: list[m.PurchaseOrderItem]) -> str:
    if not items:
        return "sent"
    fully = all(float(i.received_qty or 0) >= float(i.quantity or 0) for i in items)
    any_received = any(float(i.received_qty or 0) > 0 for i in items)
    if fully:
        return "received"
    if any_received:
        return "partially_received"
    return "sent"


async def get_supplier(db: AsyncSession, tenant_id: str, supplier_id: str) -> m.Party:
    supplier = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


async def get_po(db: AsyncSession, tenant_id: str, po_id: str) -> m.PurchaseOrder:
    po = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.id == po_id,
                m.PurchaseOrder.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


async def list_po_items(db: AsyncSession, tenant_id: str, po_id: str) -> list[m.PurchaseOrderItem]:
    return (
        await db.execute(
            select(m.PurchaseOrderItem).where(
                m.PurchaseOrderItem.tenant_id == tenant_id,
                m.PurchaseOrderItem.purchase_order_id == po_id,
            )
        )
    ).scalars().all()


def _po_line_snapshot(item: m.PurchaseOrderItem) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "quantity": float(item.quantity),
        "received_qty": float(item.received_qty or 0),
        "unit_price": float(item.unit_price or 0),
        "tax_rate": float(item.tax_rate or 0),
        "discount": float(getattr(item, "discount", 0) or 0),
        "line_total": float(item.line_total or 0),
    }


def _po_header_snapshot(po: m.PurchaseOrder) -> dict:
    return {
        "warehouse_id": po.warehouse_id,
        "delivery_address": getattr(po, "delivery_address", None),
        "notes": po.notes,
        "subtotal": float(po.subtotal or 0),
        "tax_amount": float(po.tax_amount or 0),
        "total_amount": float(po.total_amount or 0),
        "revision": int(getattr(po, "revision", 1) or 1),
        "status": po.status,
    }


async def list_po_amendments(
    db: AsyncSession, tenant_id: str, po_id: str
) -> list[m.PurchaseOrderAmendment]:
    return list(
        (
            await db.execute(
                select(m.PurchaseOrderAmendment)
                .where(
                    m.PurchaseOrderAmendment.tenant_id == tenant_id,
                    m.PurchaseOrderAmendment.purchase_order_id == po_id,
                )
                .order_by(m.PurchaseOrderAmendment.revision.desc())
            )
        )
        .scalars()
        .all()
    )


def serialize_po_amendment(row: m.PurchaseOrderAmendment) -> dict:
    return {
        "id": row.id,
        "purchase_order_id": row.purchase_order_id,
        "revision": int(row.revision),
        "reason": row.reason,
        "changed_by": row.changed_by,
        "changes": row.changes or {},
        "created_at": row.created_at,
    }


async def serialize_po(db: AsyncSession, po: m.PurchaseOrder) -> dict:
    items = await list_po_items(db, po.tenant_id, po.id)
    amendments = await list_po_amendments(db, po.tenant_id, po.id)
    return {
        "id": po.id,
        "po_number": po.po_number,
        "supplier_id": po.supplier_id,
        "warehouse_id": po.warehouse_id,
        "status": po.status,
        "subtotal": float(po.subtotal),
        "tax_amount": float(po.tax_amount),
        "total_amount": float(po.total_amount),
        "paid_amount": float(po.paid_amount or 0),
        "balance_due": max(float(po.total_amount) - float(po.paid_amount or 0), 0),
        "due_date": po.due_date,
        "delivery_address": getattr(po, "delivery_address", None),
        "notes": po.notes,
        "purchase_request_id": po.purchase_request_id,
        "sent_at": po.sent_at,
        "emailed_to": po.emailed_to,
        "revision": int(getattr(po, "revision", 1) or 1),
        "amendment_count": len(amendments),
        "created_at": po.created_at,
        "updated_at": po.updated_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "received_qty": float(i.received_qty),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(getattr(i, "discount", 0) or 0),
                "line_total": float(i.line_total),
                "outstanding_qty": max(float(i.quantity) - float(i.received_qty or 0), 0),
            }
            for i in items
        ],
    }


async def _prepare_po_lines(
    db: AsyncSession,
    *,
    tenant_id: str,
    items: list[dict],
    existing_by_id: dict[str, m.PurchaseOrderItem] | None = None,
) -> list[dict]:
    existing_by_id = existing_by_id or {}
    prepared: list[dict] = []
    for item in items:
        product_id = item.get("product_id")
        if not product_id:
            raise HTTPException(status_code=400, detail="Each line requires product_id")
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == product_id,
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")
        qty = float(item.get("quantity") or 0)
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Line quantity must be greater than zero")
        line_id = item.get("id")
        received = 0.0
        if line_id:
            existing = existing_by_id.get(str(line_id))
            if existing is None:
                raise HTTPException(status_code=404, detail=f"PO line not found: {line_id}")
            received = float(existing.received_qty or 0)
            if qty + 1e-9 < received:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot set quantity below received qty ({received}) for line {line_id}",
                )
        unit_price = float(item.get("unit_price") if item.get("unit_price") is not None else 0)
        tax_rate = float(item.get("tax_rate") or 0)
        discount = float(item.get("discount") or 0)
        line_sub, line_tax, line_total, discount = _calc_po_line_amounts(
            qty, unit_price, tax_rate, discount
        )
        prepared.append(
            {
                "id": str(line_id) if line_id else None,
                "product_id": product.id,
                "quantity": qty,
                "received_qty": received,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "discount": discount,
                "line_total": line_total,
                "line_sub": line_sub,
                "line_tax": line_tax,
            }
        )
    return prepared


async def update_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    po_id: str,
    items: list[dict] | None = None,
    warehouse_id: str | None = None,
    delivery_address=_UNSET,
    notes: str | None = None,
    reason: str | None = None,
    track_amendment: bool | None = None,
) -> m.PurchaseOrder:
    """Edit a draft PO, or amend a sent/partial PO (requires reason)."""
    po = await get_po(db, tenant_id, po_id)
    if po.status not in PO_AMENDABLE:
        raise HTTPException(status_code=409, detail=f"Cannot amend PO in status {po.status}")

    is_draft = po.status == "draft"
    if not is_draft:
        reason_clean = (reason or "").strip()
        if not reason_clean:
            raise HTTPException(status_code=400, detail="Amendment reason is required for sent POs")
    else:
        reason_clean = (reason or "").strip() or "Draft update"

    should_track = bool(track_amendment) if track_amendment is not None else (not is_draft)

    before_header = _po_header_snapshot(po)
    existing = await list_po_items(db, tenant_id, po.id)
    existing_by_id = {i.id: i for i in existing}
    before_items = [_po_line_snapshot(i) for i in existing]

    if warehouse_id is not None:
        po.warehouse_id = warehouse_id or None
    if delivery_address is not _UNSET:
        po.delivery_address = (delivery_address or None)
        if isinstance(po.delivery_address, str):
            cleaned = po.delivery_address.strip()
            po.delivery_address = cleaned or None
    if notes is not None:
        po.notes = notes

    if items is not None:
        if not items:
            raise HTTPException(status_code=400, detail="Purchase order requires at least one line item")
        prepared = await _prepare_po_lines(
            db, tenant_id=tenant_id, items=items, existing_by_id=existing_by_id
        )
        keep_ids = {p["id"] for p in prepared if p["id"]}
        for old in existing:
            if old.id not in keep_ids:
                if float(old.received_qty or 0) > 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot remove line {old.id} with received quantity",
                    )
                await db.delete(old)
        subtotal = 0.0
        tax_total = 0.0
        for prep in prepared:
            subtotal += prep["line_sub"]
            tax_total += prep["line_tax"]
            if prep["id"]:
                row = existing_by_id[prep["id"]]
                row.product_id = prep["product_id"]
                row.quantity = prep["quantity"]
                row.unit_price = prep["unit_price"]
                row.tax_rate = prep["tax_rate"]
                row.discount = prep["discount"]
                row.line_total = prep["line_total"]
            else:
                db.add(
                    m.PurchaseOrderItem(
                        tenant_id=tenant_id,
                        purchase_order_id=po.id,
                        product_id=prep["product_id"],
                        quantity=prep["quantity"],
                        received_qty=0,
                        unit_price=prep["unit_price"],
                        tax_rate=prep["tax_rate"],
                        discount=prep["discount"],
                        line_total=prep["line_total"],
                    )
                )
        po.subtotal = subtotal
        po.tax_amount = tax_total
        po.total_amount = subtotal + tax_total

    await db.flush()

    # Re-derive status if quantities changed after partial receipt
    if po.status in {"sent", "partially_received", "received"}:
        refreshed = list(await list_po_items(db, tenant_id, po.id))
        # Only auto-adjust among receivable statuses (never resurrect cancelled).
        if po.status != "cancelled":
            derived = derive_po_status(refreshed)
            if derived in {"sent", "partially_received", "received"}:
                po.status = derived

    po.updated_at = datetime.utcnow()
    after_items = [_po_line_snapshot(i) for i in await list_po_items(db, tenant_id, po.id)]
    after_header = _po_header_snapshot(po)

    if should_track:
        new_revision = int(getattr(po, "revision", 1) or 1) + 1
        po.revision = new_revision
        after_header["revision"] = new_revision
        db.add(
            m.PurchaseOrderAmendment(
                tenant_id=tenant_id,
                purchase_order_id=po.id,
                revision=new_revision,
                reason=reason_clean,
                changed_by=user_id,
                changes={
                    "before": {"header": before_header, "items": before_items},
                    "after": {"header": after_header, "items": after_items},
                },
                created_at=datetime.utcnow(),
            )
        )
        action = "po_amended"
    else:
        action = "po_updated"
        new_revision = int(getattr(po, "revision", 1) or 1)

    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        entity="purchase_order",
        entity_id=po.id,
        details={
        "po_number": po.po_number,
        "revision": new_revision,
        "reason": reason_clean if should_track else None,
        "total": float(po.total_amount or 0),
        },
        module='purchasing',
    )
    await db.flush()
    return po


async def amend_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    po_id: str,
    reason: str,
    items: list[dict] | None = None,
    warehouse_id: str | None = None,
    delivery_address=_UNSET,
    notes: str | None = None,
) -> m.PurchaseOrder:
    po = await get_po(db, tenant_id, po_id)
    kwargs = dict(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        po_id=po_id,
        items=items,
        warehouse_id=warehouse_id,
        delivery_address=delivery_address,
        notes=notes,
        reason=reason,
        track_amendment=True,
    )
    if po.status == "draft":
        # Draft amends still track when explicitly requested via /amend
        return await update_purchase_order(**kwargs)
    return await update_purchase_order(**kwargs)


async def get_purchase_request(
    db: AsyncSession, tenant_id: str, request_id: str
) -> m.PurchaseRequest:
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


async def list_pr_items(
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


async def serialize_pr(db: AsyncSession, pr: m.PurchaseRequest) -> dict:
    from app.expenses import roles_for_step

    items = await list_pr_items(db, pr.tenant_id, pr.id)
    actions = await list_pr_approval_actions(db, pr.tenant_id, pr.id)
    step = int(getattr(pr, "approval_step", 1) or 1)
    required = int(getattr(pr, "approval_steps_required", 1) or 1)
    data = {
        "id": pr.id,
        "request_number": pr.request_number,
        "supplier_id": pr.supplier_id,
        "warehouse_id": pr.warehouse_id,
        "status": pr.status,
        "department": pr.department,
        "required_date": pr.required_date,
        "notes": pr.notes,
        "rejection_reason": pr.rejection_reason,
        "estimated_total": float(getattr(pr, "estimated_total", None) or 0),
        "approval_step": step,
        "approval_steps_required": required,
        "awaiting_level": step if pr.status == "pending" else None,
        "purchase_order_id": pr.purchase_order_id,
        "created_by": pr.created_by,
        "approved_by": pr.approved_by,
        "approved_at": pr.approved_at,
        "created_at": pr.created_at,
        "updated_at": pr.updated_at,
        "approval_actions": [serialize_pr_approval_action(a) for a in actions],
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price or 0),
                "tax_rate": float(i.tax_rate or 0),
                "notes": i.notes,
            }
            for i in items
        ],
    }
    if pr.status == "pending":
        tenant = await db.get(m.Tenant, pr.tenant_id)
        levels = resolve_pr_approval_levels(tenant) if tenant else default_pr_approval_levels()
        data["awaiting_roles"] = roles_for_step(levels, step)
    return data


async def create_purchase_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str,
    items: list[dict],
    warehouse_id: str | None = None,
    department: str | None = None,
    required_date: datetime | None = None,
    notes: str | None = None,
    company_id: str | None = None,
) -> m.PurchaseRequest:
    if not items:
        raise HTTPException(status_code=400, detail="Purchase request requires at least one line item")
    await get_supplier(db, tenant_id, supplier_id)
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
        qty = float(item["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Line quantity must be greater than zero")
        unit_price = float(
            item["unit_price"] if item.get("unit_price") is not None else product.cost_price or 0
        )
        prepared.append(
            {
                "product_id": product.id,
                "quantity": qty,
                "unit_price": unit_price,
                "tax_rate": float(item.get("tax_rate") or 0),
                "notes": item.get("notes"),
            }
        )

    pr = m.PurchaseRequest(
        tenant_id=tenant_id,
        company_id=company_id,
        request_number=f"PR-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        status="draft",
        department=(department or "").strip() or None,
        required_date=required_date,
        notes=notes,
        created_by=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pr)
    await db.flush()
    for item in prepared:
        db.add(
            m.PurchaseRequestItem(
                tenant_id=tenant_id,
                purchase_request_id=pr.id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                tax_rate=item["tax_rate"],
                notes=item["notes"],
            )
        )
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="pr_created",
        entity="purchase_request",
        entity_id=pr.id,
        details={"request_number": pr.request_number},
        module='purchasing',
    )
    await db.flush()
    return pr


async def submit_purchase_request(
    db: AsyncSession, *, tenant_id: str, user_id: str, request_id: str
) -> m.PurchaseRequest:
    from app.expenses import steps_required_from_matrix

    pr = await get_purchase_request(db, tenant_id, request_id)
    if pr.status not in PR_SUBMITTABLE:
        raise HTTPException(status_code=409, detail=f"Cannot submit PR in status {pr.status}")
    items = await list_pr_items(db, tenant_id, pr.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot submit empty purchase request")

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    levels = resolve_pr_approval_levels(tenant)
    total = estimate_pr_total(items)
    steps = steps_required_from_matrix(total, levels)
    pr.estimated_total = total
    pr.updated_at = datetime.utcnow()

    if steps <= 0:
        pr.status = "approved"
        pr.approval_step = 0
        pr.approval_steps_required = 0
        pr.approved_by = user_id
        pr.approved_at = datetime.utcnow()
        pr.rejection_reason = None
        await _record_pr_action(
            db,
            tenant_id=tenant_id,
            request_id=pr.id,
            step=0,
            action="auto_approve",
            actor_id=user_id,
            comment="Below approval matrix thresholds",
        )
        from app import audit as audit_svc
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_auto_approved",
            entity="purchase_request",
            entity_id=pr.id,
            details={"request_number": pr.request_number, "estimated_total": total},
            module='purchasing',
        )
    else:
        pr.status = "pending"
        pr.approval_step = 1
        pr.approval_steps_required = steps
        pr.approved_by = None
        pr.approved_at = None
        from app import audit as audit_svc
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_submitted",
            entity="purchase_request",
            entity_id=pr.id,
            details={
            "request_number": pr.request_number,
            "estimated_total": total,
            "approval_steps_required": steps,
            },
            module='purchasing',
        )
    await db.flush()
    return pr


async def approve_purchase_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    request_id: str,
    comment: str | None = None,
    actor_role: str | None = None,
) -> m.PurchaseRequest:
    from app.expenses import assert_actor_may_act

    pr = await get_purchase_request(db, tenant_id, request_id)
    if pr.status not in PR_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot approve PR in status {pr.status}")
    if pr.created_by and pr.created_by == user_id and (actor_role or "") not in {"super_admin"}:
        raise HTTPException(status_code=403, detail="Cannot approve your own purchase request")

    step = int(pr.approval_step or 1)
    required = int(pr.approval_steps_required or 1)
    settings = await get_pr_approval_settings(db, tenant_id)
    assert_actor_may_act(levels=settings["levels"], step=step, actor_role=actor_role)

    prior = await list_pr_approval_actions(db, tenant_id, pr.id)
    if any(a.action == "approve" and a.actor_id == user_id for a in prior):
        raise HTTPException(
            status_code=403, detail="You already approved an earlier step on this purchase request"
        )

    await _record_pr_action(
        db,
        tenant_id=tenant_id,
        request_id=pr.id,
        step=step,
        action="approve",
        actor_id=user_id,
        comment=comment,
    )

    if step < required:
        pr.approval_step = step + 1
        pr.updated_at = datetime.utcnow()
        from app.notifications import create_notification

        await create_notification(
            db,
            tenant_id=tenant_id,
            category="purchase_request",
            title="Purchase Request Needs Next-Level Approval",
            message=(
                f"{pr.request_number} (est. {float(pr.estimated_total or 0):.2f}) passed level {step} "
                f"and awaits level {step + 1} approval."
            ),
            entity_type="purchase_request",
            entity_id=pr.id,
        )
        from app import audit as audit_svc
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="pr_level_approved",
            entity="purchase_request",
            entity_id=pr.id,
            details={
            "request_number": pr.request_number,
            "step": step,
            "next_step": step + 1,
            },
            module='purchasing',
        )
        await db.flush()
        return pr

    pr.status = "approved"
    pr.approved_by = user_id
    pr.approved_at = datetime.utcnow()
    pr.rejection_reason = None
    pr.approval_step = required
    pr.updated_at = datetime.utcnow()
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="pr_approved",
        entity="purchase_request",
        entity_id=pr.id,
        details={"request_number": pr.request_number, "steps": required},
        module='purchasing',
    )
    await db.flush()
    return pr


async def reject_purchase_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    request_id: str,
    reason: str | None = None,
    actor_role: str | None = None,
) -> m.PurchaseRequest:
    from app.expenses import assert_actor_may_act

    pr = await get_purchase_request(db, tenant_id, request_id)
    if pr.status not in PR_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot reject PR in status {pr.status}")
    if pr.created_by and pr.created_by == user_id and (actor_role or "") not in {"super_admin"}:
        raise HTTPException(status_code=403, detail="Cannot reject your own purchase request")

    step = int(pr.approval_step or 1)
    settings = await get_pr_approval_settings(db, tenant_id)
    assert_actor_may_act(levels=settings["levels"], step=step, actor_role=actor_role)

    await _record_pr_action(
        db,
        tenant_id=tenant_id,
        request_id=pr.id,
        step=step,
        action="reject",
        actor_id=user_id,
        comment=(reason or "").strip() or None,
    )
    pr.status = "rejected"
    pr.rejection_reason = (reason or "").strip() or None
    pr.updated_at = datetime.utcnow()
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="pr_rejected",
        entity="purchase_request",
        entity_id=pr.id,
        details={"request_number": pr.request_number, "reason": pr.rejection_reason, "step": step},
        module='purchasing',
    )
    await db.flush()
    return pr


async def cancel_purchase_request(
    db: AsyncSession, *, tenant_id: str, user_id: str, request_id: str
) -> m.PurchaseRequest:
    pr = await get_purchase_request(db, tenant_id, request_id)
    if pr.status not in PR_CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel PR in status {pr.status}")
    pr.status = "cancelled"
    pr.updated_at = datetime.utcnow()
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="pr_cancelled",
        entity="purchase_request",
        entity_id=pr.id,
        details={"request_number": pr.request_number},
        module='purchasing',
    )
    await db.flush()
    return pr


async def convert_purchase_request_to_po(
    db: AsyncSession, *, tenant_id: str, user_id: str, request_id: str
) -> tuple[m.PurchaseRequest, m.PurchaseOrder]:
    pr = await get_purchase_request(db, tenant_id, request_id)
    if pr.status not in PR_CONVERTIBLE:
        raise HTTPException(status_code=409, detail=f"Cannot convert PR in status {pr.status}")
    items = await list_pr_items(db, tenant_id, pr.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot convert empty purchase request")
    po = await create_purchase_order(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        supplier_id=pr.supplier_id,
        warehouse_id=pr.warehouse_id,
        notes=pr.notes or f"Converted from {pr.request_number}",
        items=[
            {
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price or 0),
                "tax_rate": float(i.tax_rate or 0),
            }
            for i in items
        ],
        purchase_request_id=pr.id,
        company_id=getattr(pr, "company_id", None),
    )
    pr.status = "converted"
    pr.purchase_order_id = po.id
    pr.updated_at = datetime.utcnow()
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="pr_converted",
        entity="purchase_request",
        entity_id=pr.id,
        details={"request_number": pr.request_number, "po_id": po.id, "po_number": po.po_number},
        module='purchasing',
    )
    await db.flush()
    return pr, po


async def create_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str,
    items: list[dict],
    warehouse_id: str | None = None,
    delivery_address: str | None = None,
    notes: str | None = None,
    purchase_request_id: str | None = None,
    company_id: str | None = None,
) -> m.PurchaseOrder:
    if not items:
        raise HTTPException(status_code=400, detail="Purchase order requires at least one line item")
    await get_supplier(db, tenant_id, supplier_id)
    if purchase_request_id and company_id is None:
        pr = await get_purchase_request(db, tenant_id, purchase_request_id)
        company_id = getattr(pr, "company_id", None)

    prepared = await _prepare_po_lines(db, tenant_id=tenant_id, items=items)
    subtotal = sum(p["line_sub"] for p in prepared)
    tax_total = sum(p["line_tax"] for p in prepared)
    address = (delivery_address or "").strip() or None

    from app.document_numbering import allocate_document_number

    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        company_id=company_id,
        po_number=await allocate_document_number(db, tenant_id=tenant_id, doc_key="purchase_order", company_id=company_id),
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        total_amount=subtotal + tax_total,
        delivery_address=address,
        notes=notes,
        purchase_request_id=purchase_request_id,
        revision=1,
        created_by=user_id,
    )
    db.add(po)
    await db.flush()

    for prep in prepared:
        db.add(
            m.PurchaseOrderItem(
                tenant_id=tenant_id,
                purchase_order_id=po.id,
                product_id=prep["product_id"],
                quantity=prep["quantity"],
                received_qty=0,
                unit_price=prep["unit_price"],
                tax_rate=prep["tax_rate"],
                discount=prep["discount"],
                line_total=prep["line_total"],
            )
        )

    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="po_created",
        entity="purchase_order",
        entity_id=po.id,
        details={"po_number": po.po_number, "total": float(po.total_amount)},
        module='purchasing',
    )
    return po


def render_po_text(po_data: dict, *, supplier_name: str, company_name: str) -> str:
    lines = [
        f"{company_name}",
        f"Purchase Order {po_data.get('po_number')}",
        f"Supplier: {supplier_name}",
        f"Status: {po_data.get('status')}",
    ]
    if po_data.get("delivery_address"):
        lines.append(f"Deliver to: {po_data['delivery_address']}")
    lines.extend(
        [
            "",
            f"{'Product':<28} {'Qty':>8} {'Price':>10} {'Disc':>8} {'Total':>10}",
            "-" * 72,
        ]
    )
    for item in po_data.get("items") or []:
        lines.append(
            f"{str(item.get('product_id')):<28} {float(item.get('quantity') or 0):>8.3f} "
            f"{float(item.get('unit_price') or 0):>10.2f} {float(item.get('discount') or 0):>8.2f} "
            f"{float(item.get('line_total') or 0):>10.2f}"
        )
    lines.extend(
        [
            "-" * 72,
            f"Subtotal: {float(po_data.get('subtotal') or 0):.2f}",
            f"Tax: {float(po_data.get('tax_amount') or 0):.2f}",
            f"Total: {float(po_data.get('total_amount') or 0):.2f}",
        ]
    )
    if po_data.get("notes"):
        lines.extend(["", f"Notes: {po_data['notes']}"])
    from app.print_branding import platform_print_footer_text_lines

    lines.extend(platform_print_footer_text_lines(width=72))
    return "\n".join(lines)


async def send_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    po_id: str,
    email: bool | None = None,
    to: str | None = None,
) -> tuple[m.PurchaseOrder, dict | None]:
    from app import emailer
    from app import tenants as tenants_svc

    po = await get_po(db, tenant_id, po_id)
    if po.status not in PO_EDITABLE:
        raise HTTPException(status_code=409, detail=f"Cannot send PO in status {po.status}")
    items = await list_po_items(db, tenant_id, po.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot send empty purchase order")
    supplier = await get_supplier(db, tenant_id, po.supplier_id)
    po.status = "sent"
    if po.due_date is None and int(supplier.payment_terms_days or 0) > 0:
        from datetime import timedelta

        po.due_date = datetime.utcnow() + timedelta(days=int(supplier.payment_terms_days))
    else:
        po.due_date = po.due_date or default_due_date()
    po.sent_at = datetime.utcnow()
    po.updated_at = datetime.utcnow()

    recipient = (to or supplier.email or "").strip()
    should_email = bool(email) if email is not None else bool(recipient)
    delivery = None
    if should_email:
        if not recipient:
            raise HTTPException(
                status_code=400,
                detail="Supplier has no email; pass to= or set email=false",
            )
        tenant = await tenants_svc.get_tenant(db, tenant_id)
        po_data = await serialize_po(db, po)
        result = await emailer.send_purchase_order_email(
            to=recipient,
            company_name=tenant.company_name if tenant else "RIBDIGI ERP",
            supplier_name=supplier.name,
            purchase_order=po_data,
            text_body=render_po_text(
                po_data,
                supplier_name=supplier.name,
                company_name=tenant.company_name if tenant else "RIBDIGI ERP",
            ),
        )
        delivery = {
            "to": recipient,
            "mode": result.mode,
            "sent": result.sent,
            "error": result.error,
        }
        if not result.sent and result.mode == "smtp":
            raise HTTPException(status_code=502, detail=f"Failed to email PO: {result.error}")
        po.emailed_to = recipient

    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="po_sent",
        entity="purchase_order",
        entity_id=po.id,
        details={"po_number": po.po_number, "delivery": delivery},
        module='purchasing',
    )
    await db.flush()
    return po, delivery


async def cancel_purchase_order(db: AsyncSession, *, tenant_id: str, user_id: str, po_id: str) -> m.PurchaseOrder:
    po = await get_po(db, tenant_id, po_id)
    if po.status in {"received", "cancelled"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel PO in status {po.status}")
    items = await list_po_items(db, tenant_id, po.id)
    if any(float(i.received_qty or 0) > 0 for i in items):
        raise HTTPException(status_code=409, detail="Cannot cancel PO after goods have been received")
    po.status = "cancelled"
    po.updated_at = datetime.utcnow()
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="po_cancelled",
        entity="purchase_order",
        entity_id=po.id,
        details={"po_number": po.po_number},
        module='purchasing',
    )
    return po


async def create_grn(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    purchase_order_id: str,
    items: list[dict],
    warehouse_id: str | None = None,
    notes: str | None = None,
    post_supplier_balance: bool = True,
    company_id: str | None = None,
) -> m.GoodsReceipt:
    if not items:
        raise HTTPException(status_code=400, detail="GRN requires at least one line item")

    po = await get_po(db, tenant_id, purchase_order_id)
    if po.status not in PO_RECEIVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot receive against PO in status {po.status}")

    po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}
    accepted_value = 0.0

    from app.document_numbering import allocate_document_number

    grn = m.GoodsReceipt(
        tenant_id=tenant_id,
        company_id=company_id or getattr(po, "company_id", None),
        grn_number=await allocate_document_number(db, tenant_id=tenant_id, doc_key="goods_receipt", company_id=company_id or getattr(po, "company_id", None)),
        purchase_order_id=po.id,
        supplier_id=po.supplier_id,
        warehouse_id=warehouse_id or po.warehouse_id,
        status="posted",
        notes=notes,
        created_by=user_id,
    )
    db.add(grn)
    await db.flush()

    for raw in items:
        po_item = po_items.get(raw["po_item_id"])
        if not po_item:
            raise HTTPException(status_code=400, detail=f"Invalid po_item_id: {raw['po_item_id']}")

        received_qty = float(raw.get("received_qty") or 0)
        accepted_qty = float(raw.get("accepted_qty") if raw.get("accepted_qty") is not None else received_qty)
        rejected_qty = float(raw.get("rejected_qty") or max(received_qty - accepted_qty, 0))
        if received_qty <= 0:
            raise HTTPException(status_code=400, detail="received_qty must be positive")
        if accepted_qty < 0 or rejected_qty < 0:
            raise HTTPException(status_code=400, detail="accepted/rejected qty cannot be negative")
        if accepted_qty + rejected_qty > received_qty + 1e-9:
            raise HTTPException(status_code=400, detail="accepted_qty + rejected_qty cannot exceed received_qty")

        outstanding = float(po_item.quantity) - float(po_item.received_qty or 0)
        if accepted_qty > outstanding + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVER_RECEIPT",
                    "message": f"Accepted qty exceeds outstanding for PO item {po_item.id}",
                    "outstanding": outstanding,
                    "accepted_qty": accepted_qty,
                },
            )

        batch_number = (raw.get("batch_number") or "").strip() or None
        manufacturing_date = raw.get("manufacturing_date")
        expiry_date = raw.get("expiry_date")
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == po_item.product_id,
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product not found: {po_item.product_id}")
        if accepted_qty > 0 and product.tracks_batches and not batch_number:
            raise HTTPException(
                status_code=400,
                detail=f"batch_number required for batch-tracked product {product.sku}",
            )
        if rejected_qty > 0 and not (raw.get("rejection_reason") or "").strip():
            raise HTTPException(status_code=400, detail="rejection_reason required when rejected_qty > 0")

        batch_id = None
        if accepted_qty > 0:
            if batch_number:
                stock_result = await catalog_svc.stock_in_with_batch(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    product_id=po_item.product_id,
                    quantity=accepted_qty,
                    notes=f"GRN {grn.grn_number}",
                    warehouse_id=grn.warehouse_id,
                    batch_number=batch_number,
                    manufacturing_date=manufacturing_date,
                    expiry_date=expiry_date,
                    reference_type="grn",
                    reference_id=grn.id,
                )
                batch_id = stock_result.get("batch_id")
            else:
                await apply_stock_change(
                    db,
                    tenant_id=tenant_id,
                    product_id=po_item.product_id,
                    quantity_delta=accepted_qty,
                    movement_type="stock_in",
                    user_id=user_id,
                    reference_type="grn",
                    reference_id=grn.id,
                    warehouse_id=grn.warehouse_id,
                    notes=f"GRN {grn.grn_number}",
                )
            po_item.received_qty = float(po_item.received_qty or 0) + accepted_qty
            _, _, line_total, _ = _calc_partial_po_line_amounts(
                accepted_qty,
                float(po_item.unit_price or 0),
                float(po_item.tax_rate or 0),
                float(po_item.discount or 0),
                float(po_item.quantity or 0),
            )
            accepted_value += line_total

        db.add(
            m.GoodsReceiptItem(
                tenant_id=tenant_id,
                goods_receipt_id=grn.id,
                po_item_id=po_item.id,
                product_id=po_item.product_id,
                received_qty=received_qty,
                accepted_qty=accepted_qty,
                rejected_qty=rejected_qty,
                rejection_reason=raw.get("rejection_reason"),
                batch_id=batch_id,
                batch_number=batch_number,
                manufacturing_date=manufacturing_date,
                expiry_date=expiry_date,
            )
        )

    updated_items = await list_po_items(db, tenant_id, po.id)
    po.status = derive_po_status(updated_items)
    po.updated_at = datetime.utcnow()
    accepted_value = round(float(accepted_value), 2)
    balance_before = None
    balance_after = None

    if post_supplier_balance and accepted_value > 0:
        supplier = await get_supplier(db, tenant_id, po.supplier_id)
        balance_before = float(supplier.balance or 0)
        supplier.balance = balance_before + accepted_value
        balance_after = float(supplier.balance)

    from app.accounting import post_grn_journal

    await post_grn_journal(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        grn=grn,
        accepted_value=accepted_value,
    )

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="purchase_received",
        title="Purchase received",
        message=f"GRN {grn.grn_number} posted against {po.po_number}. PO status: {po.status}.",
        entity_type="goods_receipt",
        entity_id=grn.id,
    )
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="grn_posted",
        entity="goods_receipt",
        entity_id=grn.id,
        details={
            "grn_number": grn.grn_number,
            "po_id": po.id,
            "po_status": po.status,
            "accepted_value": accepted_value,
            "supplier_id": po.supplier_id,
            "supplier_balance_before": balance_before,
            "supplier_balance_after": balance_after,
        },
        module="purchasing",
    )
    return grn


async def serialize_grn(db: AsyncSession, grn: m.GoodsReceipt) -> dict:
    items = (
        await db.execute(
            select(m.GoodsReceiptItem).where(
                m.GoodsReceiptItem.tenant_id == grn.tenant_id,
                m.GoodsReceiptItem.goods_receipt_id == grn.id,
            )
        )
    ).scalars().all()
    return {
        "id": grn.id,
        "grn_number": grn.grn_number,
        "purchase_order_id": grn.purchase_order_id,
        "supplier_id": grn.supplier_id,
        "warehouse_id": grn.warehouse_id,
        "status": grn.status,
        "notes": grn.notes,
        "created_at": grn.created_at,
        "items": [
            {
                "id": i.id,
                "po_item_id": i.po_item_id,
                "product_id": i.product_id,
                "received_qty": float(i.received_qty),
                "accepted_qty": float(i.accepted_qty),
                "rejected_qty": float(i.rejected_qty),
                "rejection_reason": i.rejection_reason,
                "batch_id": i.batch_id,
                "batch_number": i.batch_number,
                "manufacturing_date": i.manufacturing_date,
                "expiry_date": i.expiry_date,
            }
            for i in items
        ],
    }


async def record_supplier_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str,
    amount: float,
    purchase_order_id: str | None = None,
    purchase_invoice_id: str | None = None,
    payment_method: str = "bank_transfer",
    reference: str | None = None,
    notes: str | None = None,
    cheque_number: str | None = None,
    bank_name: str | None = None,
    cheque_date: datetime | None = None,
    liquid_account_id: str | None = None,
    apply_early_discount: bool | None = None,
    currency: str | None = None,
    exchange_rate: float | None = None,
    company_id: str | None = None,
) -> m.SupplierPayment:
    amount = float(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    if liquid_account_id:
        from app.accounting import resolve_settlement_gl

        await resolve_settlement_gl(
            db,
            tenant_id,
            payment_method or "bank_transfer",
            liquid_account_id=liquid_account_id,
            outflow=True,
        )

    supplier = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    tenant = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))).scalar_one()
    from app.credit import resolve_early_pay_settings, purchase_invoice_early_discount

    ep = resolve_early_pay_settings(tenant, supplier)
    use_discount = ep["enabled"] if apply_early_discount is None else bool(apply_early_discount)
    if use_discount and not ep["enabled"]:
        use_discount = False

    # (invoice, settlement_to_paid_amount, discount_portion) | PO-only handled separately
    invoice_allocations: list[tuple[m.PurchaseInvoice, float, float]] = []
    po_allocations: list[tuple[m.PurchaseOrder, float]] = []
    total_discount = 0.0

    if purchase_invoice_id:
        inv = await get_purchase_invoice(db, tenant_id, purchase_invoice_id)
        if inv.supplier_id != supplier_id:
            raise HTTPException(status_code=400, detail="Invoice does not belong to this supplier")
        if inv.status not in PURCHASE_INVOICE_OPEN and inv.status != "draft":
            raise HTTPException(status_code=409, detail=f"Cannot pay invoice in status {inv.status}")
        if inv.status == "draft":
            raise HTTPException(status_code=409, detail="Approve purchase invoice before payment")
        due = float(inv.total_amount) - float(inv.paid_amount or 0)
        quote = purchase_invoice_early_discount(
            inv, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
        )
        if use_discount and quote["eligible"] and amount + 1e-9 >= quote["cash_to_settle"]:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            if amount + 1e-9 >= due:
                invoice_allocations.append((inv, min(amount, due), 0.0))
            else:
                discount = round(due - amount, 2)
                if discount > quote["discount_amount"] + 1e-9:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Payment too low for early discount; "
                            f"need at least {quote['cash_to_settle']:.2f}"
                        ),
                    )
                invoice_allocations.append((inv, due, discount))
                total_discount = discount
        else:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            invoice_allocations.append((inv, amount, 0.0))
        if inv.purchase_order_id:
            po = await get_po(db, tenant_id, inv.purchase_order_id)
            settlement = invoice_allocations[0][1]
            po_allocations.append((po, settlement))
    elif purchase_order_id:
        po = await get_po(db, tenant_id, purchase_order_id)
        if po.supplier_id != supplier_id:
            raise HTTPException(status_code=400, detail="PO does not belong to this supplier")
        open_invs = (
            await db.execute(
                select(m.PurchaseInvoice)
                .where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.purchase_order_id == purchase_order_id,
                    m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
                )
                .order_by(m.PurchaseInvoice.due_date.asc(), m.PurchaseInvoice.created_at.asc())
            )
        ).scalars().all()
        remaining = amount
        for inv in open_invs:
            due = float(inv.total_amount) - float(inv.paid_amount or 0)
            if due <= 0:
                continue
            quote = purchase_invoice_early_discount(
                inv, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
            )
            if use_discount and quote["eligible"] and remaining + 1e-9 >= quote["cash_to_settle"]:
                settlement = due
                discount = quote["discount_amount"]
                cash_used = quote["cash_to_settle"]
                invoice_allocations.append((inv, settlement, discount))
                total_discount = round(total_discount + discount, 2)
                remaining = round(remaining - cash_used, 2)
            else:
                apply_amt = min(remaining, due)
                invoice_allocations.append((inv, apply_amt, 0.0))
                remaining = round(remaining - apply_amt, 2)
            if remaining <= 0:
                break
        due_po = float(po.total_amount) - float(po.paid_amount or 0)
        settlement_on_po = sum(s for _, s, _ in invoice_allocations) if invoice_allocations else amount
        if amount > due_po + 1e-9 and not invoice_allocations:
            raise HTTPException(status_code=409, detail="Payment exceeds PO balance due")
        po_allocations.append((po, min(settlement_on_po, due_po) if invoice_allocations else amount))
    else:
        remaining = amount
        open_invs = (
            await db.execute(
                select(m.PurchaseInvoice)
                .where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.supplier_id == supplier_id,
                    m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
                )
                .order_by(m.PurchaseInvoice.due_date.asc(), m.PurchaseInvoice.created_at.asc())
            )
        ).scalars().all()
        for inv in open_invs:
            due = float(inv.total_amount) - float(inv.paid_amount or 0)
            if due <= 0:
                continue
            quote = purchase_invoice_early_discount(
                inv, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
            )
            if use_discount and quote["eligible"] and remaining + 1e-9 >= quote["cash_to_settle"]:
                settlement = due
                discount = quote["discount_amount"]
                cash_used = quote["cash_to_settle"]
                invoice_allocations.append((inv, settlement, discount))
                total_discount = round(total_discount + discount, 2)
                if inv.purchase_order_id:
                    po = await get_po(db, tenant_id, inv.purchase_order_id)
                    po_allocations.append((po, settlement))
                remaining = round(remaining - cash_used, 2)
            else:
                apply_amt = min(remaining, due)
                invoice_allocations.append((inv, apply_amt, 0.0))
                if inv.purchase_order_id:
                    po = await get_po(db, tenant_id, inv.purchase_order_id)
                    po_allocations.append((po, apply_amt))
                remaining = round(remaining - apply_amt, 2)
            if remaining <= 0:
                break
        if remaining > 1e-9:
            open_pos = (
                await db.execute(
                    select(m.PurchaseOrder)
                    .where(
                        m.PurchaseOrder.tenant_id == tenant_id,
                        m.PurchaseOrder.supplier_id == supplier_id,
                        m.PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
                    )
                    .order_by(m.PurchaseOrder.due_date.asc(), m.PurchaseOrder.created_at.asc())
                )
            ).scalars().all()
            for po in open_pos:
                due = float(po.total_amount) - float(po.paid_amount or 0)
                if due <= 0:
                    continue
                apply_amt = min(remaining, due)
                po_allocations.append((po, apply_amt))
                remaining = round(remaining - apply_amt, 2)
                if remaining <= 0:
                    break
            if remaining > 1e-9 and (open_pos or open_invs):
                raise HTTPException(
                    status_code=409,
                    detail=f"Payment exceeds open balances by {remaining:.2f}",
                )

    primary_inv = invoice_allocations[0][0] if invoice_allocations else None
    primary_po_id = (
        purchase_order_id
        or (primary_inv.purchase_order_id if primary_inv else None)
        or (po_allocations[0][0].id if po_allocations else None)
    )

    from app.fx import doc_currency, doc_rate, resolve_rate, to_base

    if invoice_allocations:
        inv0 = invoice_allocations[0][0]
        default_cur = doc_currency(inv0, tenant.currency or "GHS")
        for inv, _s, _d in invoice_allocations[1:]:
            if doc_currency(inv, tenant.currency or "GHS") != default_cur:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot auto-allocate across mixed invoice currencies; pay per invoice",
                )
        pay_cur = (currency or default_cur).strip().upper()
        if pay_cur != default_cur:
            raise HTTPException(
                status_code=400,
                detail=f"Payment currency {pay_cur} must match invoice currency {default_cur}",
            )
        if exchange_rate is not None:
            pay_rate = float(exchange_rate)
            if pay_rate <= 0:
                raise HTTPException(status_code=400, detail="exchange_rate must be positive")
        else:
            pay_cur, pay_rate = await resolve_rate(
                db, tenant_id, default_cur, explicit_rate=doc_rate(inv0)
            )
    else:
        pay_cur, pay_rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)

    alloc_note = ", ".join(
        f"{inv.invoice_number}:{amt:.2f}" + (f"(disc {disc:.2f})" if disc else "")
        for inv, amt, disc in invoice_allocations
    )
    if invoice_allocations:
        settlement_base = round(
            sum(to_base(amt, doc_rate(inv)) for inv, amt, _ in invoice_allocations),
            2,
        )
    else:
        settlement_base = to_base(amount, pay_rate)

    payment = m.SupplierPayment(
        tenant_id=tenant_id,
        company_id=company_id or getattr(supplier, "company_id", None),
        payment_number=f"SPY-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        supplier_id=supplier_id,
        purchase_order_id=primary_po_id,
        purchase_invoice_id=primary_inv.id if primary_inv else purchase_invoice_id,
        amount=amount,
        payment_method=payment_method,
        early_payment_discount=round(total_discount, 2),
        currency=pay_cur,
        exchange_rate=pay_rate,
        liquid_account_id=liquid_account_id,
        reference=reference,
        notes=notes
        or (
            f"Auto-allocated: {alloc_note}"
            if alloc_note and not purchase_invoice_id
            else (f"Early discount {total_discount:.2f}" if total_discount else notes)
        ),
        created_by=user_id,
    )
    db.add(payment)
    supplier.balance = max(float(supplier.balance or 0) - settlement_base, 0)

    for inv, apply_amt, _disc in invoice_allocations:
        inv.paid_amount = float(inv.paid_amount or 0) + apply_amt
        inv.status = purchase_invoice_status(
            float(inv.total_amount), float(inv.paid_amount), inv.due_date
        )
        inv.updated_at = datetime.utcnow()

    # Aggregate PO applications (same PO may appear multiple times)
    po_applied: dict[str, float] = {}
    for po, apply_amt in po_allocations:
        po_applied[po.id] = po_applied.get(po.id, 0.0) + apply_amt
    for po_id, apply_amt in po_applied.items():
        po = await get_po(db, tenant_id, po_id)
        po.paid_amount = float(po.paid_amount or 0) + apply_amt
        po.updated_at = datetime.utcnow()

    from app.accounting import post_supplier_payment_journal

    await post_supplier_payment_journal(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payment=payment,
        allocations=invoice_allocations or None,
    )

    from app import cheques as cheques_svc

    await cheques_svc.create_from_supplier_payment(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payment=payment,
        cheque_number=cheque_number,
        bank_name=bank_name,
        cheque_date=cheque_date,
    )
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="supplier_payment_recorded",
        entity="supplier_payment",
        entity_id=payment.id,
        details={
            "payment_number": payment.payment_number,
            "supplier_id": supplier_id,
            "amount": float(payment.amount),
            "settlement_base": float(settlement_base),
            "supplier_balance_after": float(supplier.balance or 0),
            "purchase_invoice_id": payment.purchase_invoice_id,
            "purchase_order_id": payment.purchase_order_id,
            "payment_method": payment.payment_method,
            "currency": payment.currency,
        },
        module="purchasing",
    )
    return payment


# --- Purchase returns / debit notes ---


async def get_grn(db: AsyncSession, tenant_id: str, grn_id: str) -> m.GoodsReceipt:
    grn = (
        await db.execute(
            select(m.GoodsReceipt).where(
                m.GoodsReceipt.id == grn_id,
                m.GoodsReceipt.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    return grn


async def list_grn_items(db: AsyncSession, tenant_id: str, grn_id: str) -> list[m.GoodsReceiptItem]:
    return (
        await db.execute(
            select(m.GoodsReceiptItem).where(
                m.GoodsReceiptItem.tenant_id == tenant_id,
                m.GoodsReceiptItem.goods_receipt_id == grn_id,
            )
        )
    ).scalars().all()


async def get_purchase_return(db: AsyncSession, tenant_id: str, return_id: str) -> m.PurchaseReturn:
    row = (
        await db.execute(
            select(m.PurchaseReturn).where(
                m.PurchaseReturn.id == return_id,
                m.PurchaseReturn.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    return row


async def list_purchase_return_items(
    db: AsyncSession, tenant_id: str, return_id: str
) -> list[m.PurchaseReturnItem]:
    return (
        await db.execute(
            select(m.PurchaseReturnItem).where(
                m.PurchaseReturnItem.tenant_id == tenant_id,
                m.PurchaseReturnItem.purchase_return_id == return_id,
            )
        )
    ).scalars().all()


async def _returned_qty_by_grn_item(
    db: AsyncSession,
    *,
    tenant_id: str,
    goods_receipt_id: str,
    exclude_return_id: str | None = None,
) -> dict[str, float]:
    """Sum return qty for GRN lines across draft+posted returns (exclude cancelled)."""
    q = (
        select(m.PurchaseReturnItem.goods_receipt_item_id, m.PurchaseReturnItem.quantity)
        .join(m.PurchaseReturn, m.PurchaseReturn.id == m.PurchaseReturnItem.purchase_return_id)
        .where(
            m.PurchaseReturnItem.tenant_id == tenant_id,
            m.PurchaseReturn.goods_receipt_id == goods_receipt_id,
            m.PurchaseReturn.status.in_(["draft", "posted"]),
        )
    )
    if exclude_return_id:
        q = q.where(m.PurchaseReturn.id != exclude_return_id)
    rows = (await db.execute(q)).all()
    totals: dict[str, float] = {}
    for item_id, qty in rows:
        totals[item_id] = totals.get(item_id, 0.0) + float(qty or 0)
    return totals


async def serialize_purchase_return(db: AsyncSession, ret: m.PurchaseReturn) -> dict:
    items = await list_purchase_return_items(db, ret.tenant_id, ret.id)
    return {
        "id": ret.id,
        "return_number": ret.return_number,
        "debit_note_number": ret.debit_note_number,
        "supplier_id": ret.supplier_id,
        "purchase_order_id": ret.purchase_order_id,
        "goods_receipt_id": ret.goods_receipt_id,
        "warehouse_id": ret.warehouse_id,
        "status": ret.status,
        "reason": ret.reason,
        "subtotal": float(ret.subtotal),
        "tax_amount": float(ret.tax_amount),
        "total_amount": float(ret.total_amount),
        "notes": ret.notes,
        "posted_at": ret.posted_at,
        "created_at": ret.created_at,
        "items": [
            {
                "id": i.id,
                "goods_receipt_item_id": i.goods_receipt_item_id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


async def create_purchase_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    goods_receipt_id: str,
    items: list[dict],
    reason: str = "other",
    notes: str | None = None,
    company_id: str | None = None,
) -> m.PurchaseReturn:
    if reason not in PURCHASE_RETURN_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"reason must be one of {sorted(PURCHASE_RETURN_REASONS)}",
        )
    if not items:
        raise HTTPException(status_code=400, detail="Return requires line items")

    grn = await get_grn(db, tenant_id, goods_receipt_id)
    if grn.status != "posted":
        raise HTTPException(status_code=409, detail="Returns require a posted GRN")

    grn_items = {i.id: i for i in await list_grn_items(db, tenant_id, grn.id)}
    already = await _returned_qty_by_grn_item(db, tenant_id=tenant_id, goods_receipt_id=grn.id)
    po = await get_po(db, tenant_id, grn.purchase_order_id)
    po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}

    subtotal = 0.0
    tax_total = 0.0
    prepared: list[dict] = []
    for raw in items:
        grn_item_id = raw.get("goods_receipt_item_id")
        grn_item = grn_items.get(grn_item_id)
        if not grn_item:
            raise HTTPException(status_code=400, detail=f"Invalid goods_receipt_item_id: {grn_item_id}")
        qty = float(raw["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be positive")
        available = float(grn_item.accepted_qty or 0) - already.get(grn_item.id, 0.0)
        if qty > available + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVER_RETURN",
                    "message": f"Return qty exceeds remaining accepted qty for GRN line {grn_item.id}",
                    "available": available,
                    "requested": qty,
                },
            )
        po_item = po_items.get(grn_item.po_item_id)
        if not po_item:
            raise HTTPException(status_code=400, detail="GRN line missing PO item")
        unit = float(po_item.unit_price)
        rate = float(po_item.tax_rate or 0)
        line_net = round(qty * unit, 2)
        line_tax = round(line_net * (rate / 100.0), 2)
        line_total = round(line_net + line_tax, 2)
        subtotal += line_net
        tax_total += line_tax
        prepared.append(
            {
                "goods_receipt_item_id": grn_item.id,
                "product_id": grn_item.product_id,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "line_total": line_total,
            }
        )
        already[grn_item.id] = already.get(grn_item.id, 0.0) + qty

    from app.document_numbering import allocate_document_number

    ret = m.PurchaseReturn(
        tenant_id=tenant_id,
        company_id=company_id or getattr(grn, "company_id", None),
        return_number=await allocate_document_number(
            db,
            tenant_id=tenant_id,
            doc_key="purchase_return",
            company_id=company_id or getattr(grn, "company_id", None),
        ),
        supplier_id=grn.supplier_id,
        purchase_order_id=grn.purchase_order_id,
        goods_receipt_id=grn.id,
        warehouse_id=grn.warehouse_id,
        status="draft",
        reason=reason,
        subtotal=round(subtotal, 2),
        tax_amount=round(tax_total, 2),
        total_amount=round(subtotal + tax_total, 2),
        notes=notes,
        created_by=user_id,
    )
    db.add(ret)
    await db.flush()
    for line in prepared:
        db.add(m.PurchaseReturnItem(tenant_id=tenant_id, purchase_return_id=ret.id, **line))
    await db.flush()
    return ret


async def post_purchase_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    return_id: str,
) -> m.PurchaseReturn:
    ret = await get_purchase_return(db, tenant_id, return_id)
    if ret.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post return in status {ret.status}")
    items = await list_purchase_return_items(db, tenant_id, ret.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty return")

    # Re-validate remaining accepted qty excluding this draft
    already = await _returned_qty_by_grn_item(
        db,
        tenant_id=tenant_id,
        goods_receipt_id=ret.goods_receipt_id,
        exclude_return_id=ret.id,
    )
    grn_items = {i.id: i for i in await list_grn_items(db, tenant_id, ret.goods_receipt_id)}
    po = await get_po(db, tenant_id, ret.purchase_order_id)
    po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}

    for item in items:
        grn_item = grn_items.get(item.goods_receipt_item_id)
        if not grn_item:
            raise HTTPException(status_code=400, detail="GRN line missing for return item")
        available = float(grn_item.accepted_qty or 0) - already.get(grn_item.id, 0.0)
        if float(item.quantity) > available + 1e-9:
            raise HTTPException(status_code=409, detail="Return quantity no longer available")
        already[grn_item.id] = already.get(grn_item.id, 0.0) + float(item.quantity)

        await apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=item.product_id,
            quantity_delta=-float(item.quantity),
            movement_type="stock_out",
            user_id=user_id,
            reference_type="purchase_return",
            reference_id=ret.id,
            warehouse_id=ret.warehouse_id,
            notes=f"Purchase return {ret.return_number}",
        )

        po_item = po_items.get(grn_item.po_item_id)
        if po_item:
            po_item.received_qty = max(float(po_item.received_qty or 0) - float(item.quantity), 0)

    updated_items = await list_po_items(db, tenant_id, po.id)
    if po.status not in {"cancelled", "draft"}:
        po.status = derive_po_status(updated_items)
        po.updated_at = datetime.utcnow()

    # Credit against open AP (mirror sales return increasing invoice paid_amount)
    credit = float(ret.total_amount)
    po.paid_amount = min(float(po.total_amount), float(po.paid_amount or 0) + credit)
    po.updated_at = datetime.utcnow()

    supplier = await get_supplier(db, tenant_id, ret.supplier_id)
    supplier.balance = max(float(supplier.balance or 0) - credit, 0)

    ret.status = "posted"
    ret.posted_at = datetime.utcnow()
    from app.document_numbering import allocate_document_number

    ret.debit_note_number = await allocate_document_number(
        db,
        tenant_id=tenant_id,
        doc_key="purchase_debit_note",
        company_id=getattr(ret, "company_id", None),
    )

    from app.accounting import post_purchase_return_journal

    await post_purchase_return_journal(db, tenant_id=tenant_id, user_id=user_id, purchase_return=ret)

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Purchase return posted",
        message=f"Return {ret.return_number} / {ret.debit_note_number} for {credit:.2f}.",
        entity_type="purchase_return",
        entity_id=ret.id,
    )
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="purchase_return_posted",
        entity="purchase_return",
        entity_id=ret.id,
        details={
        "return_number": ret.return_number,
        "debit_note_number": ret.debit_note_number,
        "total_amount": credit,
        "reason": ret.reason,
        },
        module='purchasing',
    )
    await db.flush()
    return ret


def render_debit_note_text(
    return_data: dict,
    *,
    supplier_name: str,
    company_name: str,
    po_number: str | None = None,
    grn_number: str | None = None,
) -> str:
    dn = return_data.get("debit_note_number") or "—"
    lines = [
        f"{company_name}",
        f"DEBIT NOTE {dn}",
        f"Return: {return_data.get('return_number')}",
        f"Supplier: {supplier_name}",
        f"Status: {return_data.get('status')}",
        f"Reason: {return_data.get('reason')}",
    ]
    if po_number:
        lines.append(f"PO: {po_number}")
    if grn_number:
        lines.append(f"GRN: {grn_number}")
    if return_data.get("posted_at"):
        lines.append(f"Posted: {str(return_data['posted_at'])[:19]}")
    lines.extend(
        [
            "",
            f"{'Product':<36} {'Qty':>10} {'Price':>12} {'Total':>12}",
            "-" * 72,
        ]
    )
    for item in return_data.get("items") or []:
        lines.append(
            f"{str(item.get('product_id')):<36} {float(item.get('quantity') or 0):>10.3f} "
            f"{float(item.get('unit_price') or 0):>12.2f} {float(item.get('line_total') or 0):>12.2f}"
        )
    lines.extend(
        [
            "-" * 72,
            f"Subtotal: {float(return_data.get('subtotal') or 0):.2f}",
            f"Tax: {float(return_data.get('tax_amount') or 0):.2f}",
            f"Total credit: {float(return_data.get('total_amount') or 0):.2f}",
        ]
    )
    if return_data.get("notes"):
        lines.extend(["", f"Notes: {return_data['notes']}"])
    from app.print_branding import platform_print_footer_text_lines

    lines.extend(platform_print_footer_text_lines(width=72))
    return "\n".join(lines)


# --- Purchase invoices ---


async def get_purchase_invoice(db: AsyncSession, tenant_id: str, invoice_id: str) -> m.PurchaseInvoice:
    row = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.id == invoice_id,
                m.PurchaseInvoice.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase invoice not found")
    return row


async def list_purchase_invoice_items(
    db: AsyncSession, tenant_id: str, invoice_id: str
) -> list[m.PurchaseInvoiceItem]:
    return (
        await db.execute(
            select(m.PurchaseInvoiceItem).where(
                m.PurchaseInvoiceItem.tenant_id == tenant_id,
                m.PurchaseInvoiceItem.purchase_invoice_id == invoice_id,
            )
        )
    ).scalars().all()


async def serialize_purchase_invoice(db: AsyncSession, inv: m.PurchaseInvoice) -> dict:
    items = await list_purchase_invoice_items(db, inv.tenant_id, inv.id)
    status = inv.status
    if status in PURCHASE_INVOICE_OPEN:
        status = purchase_invoice_status(float(inv.total_amount), float(inv.paid_amount or 0), inv.due_date)
        if status != inv.status:
            inv.status = status
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "supplier_id": inv.supplier_id,
        "purchase_order_id": inv.purchase_order_id,
        "goods_receipt_id": inv.goods_receipt_id,
        "supplier_invoice_number": inv.supplier_invoice_number,
        "status": status,
        "invoice_date": inv.invoice_date,
        "due_date": inv.due_date,
        "subtotal": float(inv.subtotal),
        "tax_amount": float(inv.tax_amount),
        "reverse_charge_tax": float(getattr(inv, "reverse_charge_tax", 0) or 0),
        "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
        "discount_amount": float(inv.discount_amount or 0),
        "currency": getattr(inv, "currency", None) or "",
        "exchange_rate": float(getattr(inv, "exchange_rate", None) or 1),
        "balance_due_base": round(
            max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
            * float(getattr(inv, "exchange_rate", None) or 1),
            2,
        ),
        "total_amount": float(inv.total_amount),
        "paid_amount": float(inv.paid_amount or 0),
        "balance_due": max(float(inv.total_amount) - float(inv.paid_amount or 0), 0),
        "ap_posted": bool(inv.ap_posted),
        "attachment_url": inv.attachment_url,
        "has_attachment": bool(inv.attachment_url),
        "notes": inv.notes,
        "approved_at": inv.approved_at,
        "created_at": inv.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount or 0),
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


async def _prepare_invoice_lines(
    db: AsyncSession, tenant_id: str, items: list[dict]
) -> tuple[float, float, float, list[dict]]:
    subtotal = 0.0
    tax_total = 0.0
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
        qty = float(item["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Line quantity must be positive")
        unit = float(item.get("unit_price") if item.get("unit_price") is not None else product.cost_price or 0)
        rate = float(item.get("tax_rate") or 0)
        discount = float(item.get("discount") or 0)
        # Stage 11 C1 — same tax-on-net-after-discount math as PO / GRN valuation.
        line_sub, line_tax, line_total, discount = _calc_po_line_amounts(
            qty, unit, rate, discount
        )
        subtotal += line_sub
        tax_total += line_tax
        prepared.append(
            {
                "product_id": product.id,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "discount": discount,
                "line_total": line_total,
            }
        )
    return round(subtotal, 2), round(tax_total, 2), round(subtotal + tax_total, 2), prepared


async def create_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str | None = None,
    goods_receipt_id: str | None = None,
    purchase_order_id: str | None = None,
    items: list[dict] | None = None,
    supplier_invoice_number: str | None = None,
    invoice_date: datetime | None = None,
    due_date: datetime | None = None,
    discount_amount: float = 0,
    attachment_url: str | None = None,
    notes: str | None = None,
    is_reverse_charge: bool = False,
    currency: str | None = None,
    exchange_rate: float | None = None,
    company_id: str | None = None,
) -> m.PurchaseInvoice:
    grn = None
    po = None
    from app.fx import resolve_rate

    cur, rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)
    if goods_receipt_id:
        grn = await get_grn(db, tenant_id, goods_receipt_id)
        existing = (
            await db.execute(
                select(m.PurchaseInvoice).where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.goods_receipt_id == grn.id,
                    m.PurchaseInvoice.status != "cancelled",
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="GRN already has a purchase invoice")
        po = await get_po(db, tenant_id, grn.purchase_order_id)
        supplier_id = grn.supplier_id
        purchase_order_id = po.id
        if not items:
            po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}
            items = []
            for gi in await list_grn_items(db, tenant_id, grn.id):
                qty = float(gi.accepted_qty or 0)
                if qty <= 0:
                    continue
                poi = po_items.get(gi.po_item_id)
                ordered = float(poi.quantity or 0) if poi else 0
                line_disc = float(poi.discount or 0) if poi else 0
                scaled_disc = (
                    round(line_disc * (qty / ordered), 2)
                    if poi and ordered > 0 and line_disc > 0
                    else 0.0
                )
                items.append(
                    {
                        "product_id": gi.product_id,
                        "quantity": qty,
                        "unit_price": float(poi.unit_price) if poi else 0,
                        "tax_rate": float(poi.tax_rate or 0) if poi else 0,
                        "discount": scaled_disc,
                    }
                )
    elif purchase_order_id:
        po = await get_po(db, tenant_id, purchase_order_id)
        supplier_id = supplier_id or po.supplier_id

    if not supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id is required")
    await get_supplier(db, tenant_id, supplier_id)
    if not items:
        raise HTTPException(status_code=400, detail="Invoice requires line items")

    subtotal, tax_total, gross, prepared = await _prepare_invoice_lines(db, tenant_id, items)
    discount_amount = float(discount_amount or 0)
    is_rc = bool(is_reverse_charge)
    if is_rc:
        # Supplier invoice is net; tax is self-assessed and excluded from AP.
        total = max(subtotal - discount_amount, 0)
        charged_tax = 0.0
        rc_tax = round(tax_total, 2)
    else:
        total = max(gross - discount_amount, 0)
        charged_tax = round(tax_total, 2)
        rc_tax = 0.0
    inv_date = invoice_date or datetime.utcnow()
    if due_date is None:
        due_date = default_due_date(inv_date)

    from app.document_numbering import allocate_document_number

    inv = m.PurchaseInvoice(
        tenant_id=tenant_id,
        company_id=company_id or (getattr(grn, "company_id", None) if grn else None) or (getattr(po, "company_id", None) if po else None),
        invoice_number=await allocate_document_number(
            db,
            tenant_id=tenant_id,
            doc_key="purchase_invoice",
            company_id=company_id
            or (getattr(grn, "company_id", None) if grn else None)
            or (getattr(po, "company_id", None) if po else None),
        ),
        supplier_id=supplier_id,
        purchase_order_id=purchase_order_id or (po.id if po else None),
        goods_receipt_id=grn.id if grn else None,
        supplier_invoice_number=supplier_invoice_number,
        status="draft",
        invoice_date=inv_date,
        due_date=due_date,
        subtotal=round(subtotal, 2),
        tax_amount=charged_tax,
        reverse_charge_tax=rc_tax,
        is_reverse_charge=is_rc,
        discount_amount=round(discount_amount, 2),
        total_amount=round(total, 2),
        paid_amount=0,
        currency=cur,
        exchange_rate=rate,
        ap_posted=False,
        attachment_url=attachment_url,
        notes=notes,
        created_by=user_id,
    )
    db.add(inv)
    await db.flush()
    for line in prepared:
        db.add(m.PurchaseInvoiceItem(tenant_id=tenant_id, purchase_invoice_id=inv.id, **line))
    await db.flush()
    return inv


async def approve_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
) -> m.PurchaseInvoice:
    inv = await get_purchase_invoice(db, tenant_id, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot approve invoice in status {inv.status}")
    items = await list_purchase_invoice_items(db, tenant_id, inv.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot approve empty invoice")

    # GRN path already posted inventory + AP; manual bills post AP now.
    # Stage 11 C2: GRN-linked reverse charge still needs Dr 1300 / Cr 2100 self-assess.
    if inv.goods_receipt_id:
        inv.ap_posted = False
        from app.accounting import post_purchase_invoice_journal

        await post_purchase_invoice_journal(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            purchase_invoice=inv,
            skip_inventory_ap=True,
        )
    else:
        from app.fx import doc_rate, to_base

        supplier = await get_supplier(db, tenant_id, inv.supplier_id)
        supplier.balance = float(supplier.balance or 0) + to_base(
            float(inv.total_amount), doc_rate(inv)
        )
        from app.accounting import post_purchase_invoice_journal

        await post_purchase_invoice_journal(
            db, tenant_id=tenant_id, user_id=user_id, purchase_invoice=inv
        )
        inv.ap_posted = True

    inv.status = purchase_invoice_status(float(inv.total_amount), float(inv.paid_amount or 0), inv.due_date)
    inv.approved_at = datetime.utcnow()
    inv.updated_at = datetime.utcnow()

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Purchase invoice approved",
        message=f"Invoice {inv.invoice_number} approved for {float(inv.total_amount):.2f}.",
        entity_type="purchase_invoice",
        entity_id=inv.id,
    )
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="purchase_invoice_approved",
        entity="purchase_invoice",
        entity_id=inv.id,
        details={
        "invoice_number": inv.invoice_number,
        "total": float(inv.total_amount),
        "ap_posted": inv.ap_posted,
        "goods_receipt_id": inv.goods_receipt_id,
        "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
        "reverse_charge_tax": float(getattr(inv, "reverse_charge_tax", 0) or 0),
        },
        module='purchasing',
    )
    await db.flush()
    return inv


async def cancel_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
) -> m.PurchaseInvoice:
    inv = await get_purchase_invoice(db, tenant_id, invoice_id)
    if inv.status == "cancelled":
        return inv
    if float(inv.paid_amount or 0) > 0:
        raise HTTPException(status_code=409, detail="Cannot cancel invoice with payments")
    if inv.status not in {"draft", "unpaid", "overdue"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel invoice in status {inv.status}")
    if inv.ap_posted and inv.status != "draft":
        supplier = await get_supplier(db, tenant_id, inv.supplier_id)
        supplier.balance = max(float(supplier.balance or 0) - float(inv.total_amount), 0)
        from app.accounting import post_purchase_invoice_reversal_journal

        await post_purchase_invoice_reversal_journal(
            db, tenant_id=tenant_id, user_id=user_id, purchase_invoice=inv
        )
    elif (
        inv.goods_receipt_id
        and inv.status != "draft"
        and bool(getattr(inv, "is_reverse_charge", False))
        and float(getattr(inv, "reverse_charge_tax", 0) or 0) > 0
    ):
        # Stage 11 C2 — undo RC self-assess only; GRN still owns Inv/AP + supplier balance.
        from app.accounting import post_purchase_invoice_reversal_journal

        await post_purchase_invoice_reversal_journal(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            purchase_invoice=inv,
            skip_inventory_ap=True,
        )
    prior_status = inv.status
    inv.status = "cancelled"
    inv.updated_at = datetime.utcnow()
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="purchase_invoice_cancelled",
        entity="purchase_invoice",
        entity_id=inv.id,
        details={
            "invoice_number": inv.invoice_number,
            "prior_status": prior_status,
            "total": float(inv.total_amount or 0),
            "ap_posted": bool(inv.ap_posted),
            "goods_receipt_id": inv.goods_receipt_id,
            "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
        },
        module="purchasing",
    )
    await db.flush()
    return inv
