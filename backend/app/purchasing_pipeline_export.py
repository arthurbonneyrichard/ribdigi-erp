"""CSV export for purchase requests, orders, and GRNs (Stage 134). Header-only."""

from __future__ import annotations

import csv
import io

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import purchasing as purchasing_svc
from app.rbac import apply_created_by_scope
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

PR_STATUSES = {"draft", "pending", "approved", "rejected", "cancelled", "converted"}
PO_STATUSES = {"draft", "sent", "partially_received", "received", "cancelled", "open"}
GRN_STATUSES = {"draft", "posted"}


async def export_purchase_requests_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.PurchaseRequest)
        .where(m.PurchaseRequest.tenant_id == tenant_id)
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
        .where(m.PurchaseOrder.tenant_id == tenant_id)
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
        .where(m.GoodsReceipt.tenant_id == tenant_id)
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
