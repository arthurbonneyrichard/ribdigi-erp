"""CSV export for purchase requests, orders, GRNs (Stage 134), and returns (Stage 135). Header-only."""

from __future__ import annotations

import csv
import io

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import purchasing as purchasing_svc
from app.rbac import apply_created_by_scope
from app import workspace as workspace_svc
from app.session_passkey_doc_export import _cell

PR_EXPORT_COLUMNS = [
    "request_number",
    "supplier_id",
    "warehouse_id",
    "status",
    "department",
    "required_date",
    "estimated_total",
    "approval_step",
    "approval_steps_required",
    "purchase_order_id",
    "rejection_reason",
    "created_by",
    "approved_by",
    "approved_at",
    "created_at",
]

PO_EXPORT_COLUMNS = [
    "po_number",
    "supplier_id",
    "warehouse_id",
    "status",
    "subtotal",
    "tax_amount",
    "total_amount",
    "paid_amount",
    "balance_due",
    "due_date",
    "purchase_request_id",
    "revision",
    "amendment_count",
    "sent_at",
    "emailed_to",
    "created_at",
]

GRN_EXPORT_COLUMNS = [
    "grn_number",
    "purchase_order_id",
    "supplier_id",
    "warehouse_id",
    "status",
    "notes",
    "created_at",
]

RETURN_EXPORT_COLUMNS = [
    "return_number",
    "debit_note_number",
    "supplier_id",
    "purchase_order_id",
    "goods_receipt_id",
    "warehouse_id",
    "status",
    "reason",
    "subtotal",
    "tax_amount",
    "total_amount",
    "notes",
    "posted_at",
    "created_at",
]

PO_AMENDMENT_EXPORT_COLUMNS = [
    "id",
    "purchase_order_id",
    "po_number",
    "revision",
    "reason",
    "changed_by",
    "before_total",
    "after_total",
    "created_at",
]

PR_STATUSES = {"draft", "pending", "approved", "rejected", "cancelled", "converted"}
PO_STATUSES = {"draft", "sent", "partially_received", "received", "cancelled", "open"}
GRN_STATUSES = {"draft", "posted"}
RETURN_STATUSES = {"draft", "posted"}


async def export_purchase_requests_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.PurchaseRequest)
        .where(*workspace_svc.company_scope_filter(m.PurchaseRequest, claims))
        .order_by(m.PurchaseRequest.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in PR_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status must be draft, pending, approved, rejected, cancelled, or converted",
            )
        stmt = stmt.where(m.PurchaseRequest.status == key)
    stmt = apply_created_by_scope(stmt, m.PurchaseRequest, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PR_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await purchasing_svc.serialize_pr(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in PR_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_purchase_orders_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.PurchaseOrder)
        .where(*workspace_svc.company_scope_filter(m.PurchaseOrder, claims))
        .order_by(m.PurchaseOrder.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in PO_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status must be draft, sent, partially_received, received, cancelled, or open",
            )
        if key == "open":
            stmt = stmt.where(m.PurchaseOrder.status.in_(["sent", "partially_received"]))
        else:
            stmt = stmt.where(m.PurchaseOrder.status == key)
    stmt = apply_created_by_scope(stmt, m.PurchaseOrder, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PO_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await purchasing_svc.serialize_po(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in PO_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_grns_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.GoodsReceipt)
        .where(*workspace_svc.company_scope_filter(m.GoodsReceipt, claims))
        .order_by(m.GoodsReceipt.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in GRN_STATUSES:
            raise HTTPException(status_code=400, detail="status must be draft or posted")
        stmt = stmt.where(m.GoodsReceipt.status == key)
    stmt = apply_created_by_scope(stmt, m.GoodsReceipt, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=GRN_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await purchasing_svc.serialize_grn(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in GRN_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_purchase_returns_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.PurchaseReturn)
        .where(*workspace_svc.company_scope_filter(m.PurchaseReturn, claims))
        .order_by(m.PurchaseReturn.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in RETURN_STATUSES:
            raise HTTPException(status_code=400, detail="status must be draft or posted")
        stmt = stmt.where(m.PurchaseReturn.status == key)
    stmt = apply_created_by_scope(stmt, m.PurchaseReturn, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=RETURN_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await purchasing_svc.serialize_purchase_return(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in RETURN_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_po_amendments_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    po_id: str,
) -> str:
    """Stage 154 A1 — purchase order amendment history CSV."""
    po = await purchasing_svc.get_po(db, tenant_id, po_id)
    from app.rbac import assert_record_access
    from app import workspace as workspace_svc

    assert_record_access(claims, po.created_by)
    workspace_svc.assert_record_company(claims, po)
    rows = await purchasing_svc.list_po_amendments(db, tenant_id, po_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PO_AMENDMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = purchasing_svc.serialize_po_amendment(row)
        changes = data.get("changes") if isinstance(data.get("changes"), dict) else {}
        before = (changes.get("before") or {}).get("header") if isinstance(changes.get("before"), dict) else {}
        after = (changes.get("after") or {}).get("header") if isinstance(changes.get("after"), dict) else {}
        if not isinstance(before, dict):
            before = {}
        if not isinstance(after, dict):
            after = {}
        writer.writerow(
            {
                "id": _cell(data.get("id")),
                "purchase_order_id": _cell(data.get("purchase_order_id")),
                "po_number": _cell(getattr(po, "po_number", None)),
                "revision": _cell(data.get("revision")),
                "reason": _cell(data.get("reason")),
                "changed_by": _cell(data.get("changed_by")),
                "before_total": _cell(before.get("total_amount")),
                "after_total": _cell(after.get("total_amount")),
                "created_at": _cell(data.get("created_at")),
            }
        )
    return buf.getvalue()
