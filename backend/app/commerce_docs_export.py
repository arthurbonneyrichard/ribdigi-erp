"""CSV export for sales invoices, purchase invoices, and stock transfers (Stage 132). Header-only."""

from __future__ import annotations

import csv
import io

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import purchasing as purchasing_svc
from app import sales as sales_svc
from app import stores as stores_svc
from app.rbac import apply_created_by_scope
from app.session_passkey_doc_export import _cell

SALES_INVOICE_EXPORT_COLUMNS = [
    "invoice_number",
    "customer_id",
    "store_id",
    "status",
    "is_overdue",
    "subtotal",
    "tax_amount",
    "discount_amount",
    "total_amount",
    "paid_amount",
    "balance_due",
    "currency",
    "exchange_rate",
    "due_date",
    "posted_at",
    "emailed_at",
    "sales_order_id",
    "quotation_id",
    "created_at",
]

PURCHASE_INVOICE_EXPORT_COLUMNS = [
    "invoice_number",
    "supplier_id",
    "purchase_order_id",
    "goods_receipt_id",
    "supplier_invoice_number",
    "status",
    "invoice_date",
    "due_date",
    "subtotal",
    "tax_amount",
    "discount_amount",
    "total_amount",
    "paid_amount",
    "balance_due",
    "currency",
    "exchange_rate",
    "ap_posted",
    "has_attachment",
    "approved_at",
    "created_at",
]

STOCK_TRANSFER_EXPORT_COLUMNS = [
    "transfer_number",
    "status",
    "from_store_id",
    "to_store_id",
    "from_warehouse_id",
    "to_warehouse_id",
    "notes",
    "created_by",
    "shipped_by",
    "received_by",
    "shipped_at",
    "received_at",
    "created_at",
]

SALES_INVOICE_STATUSES = {
    "draft",
    "posted",
    "sent",
    "paid",
    "partial",
    "overdue",
    "cancelled",
    "unpaid",
}
PURCHASE_INVOICE_STATUSES = {
    "draft",
    "unpaid",
    "partial",
    "overdue",
    "paid",
    "cancelled",
    "outstanding",
}
TRANSFER_STATUSES = {"draft", "requested", "in_transit", "received", "cancelled"}


async def export_sales_invoices_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    from app import workspace as workspace_svc

    stmt = (
        select(m.SalesInvoice)
        .where(*workspace_svc.company_scope_filter(m.SalesInvoice, claims))
        .order_by(m.SalesInvoice.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in SALES_INVOICE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status must be draft, posted, sent, paid, partial, unpaid, overdue, or cancelled",
            )
        if key == "unpaid":
            stmt = stmt.where(m.SalesInvoice.status.in_(["posted", "sent"]))
        else:
            stmt = stmt.where(m.SalesInvoice.status == key)
    stmt = apply_created_by_scope(stmt, m.SalesInvoice, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SALES_INVOICE_EXPORT_COLUMNS)
    writer.writeheader()
    for inv in rows:
        data = await sales_svc.serialize_invoice(db, inv)
        writer.writerow({k: _cell(data.get(k)) for k in SALES_INVOICE_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_purchase_invoices_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    from app import workspace as workspace_svc

    stmt = (
        select(m.PurchaseInvoice)
        .where(*workspace_svc.company_scope_filter(m.PurchaseInvoice, claims))
        .order_by(m.PurchaseInvoice.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in PURCHASE_INVOICE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status must be draft, unpaid, partial, overdue, paid, cancelled, or outstanding",
            )
        if key == "outstanding":
            stmt = stmt.where(
                m.PurchaseInvoice.status.in_(list(purchasing_svc.PURCHASE_INVOICE_OPEN))
            )
        else:
            stmt = stmt.where(m.PurchaseInvoice.status == key)
    stmt = apply_created_by_scope(stmt, m.PurchaseInvoice, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PURCHASE_INVOICE_EXPORT_COLUMNS)
    writer.writeheader()
    for inv in rows:
        data = await purchasing_svc.serialize_purchase_invoice(db, inv)
        writer.writerow({k: _cell(data.get(k)) for k in PURCHASE_INVOICE_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_stock_transfers_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    store_id: str | None = None,
    scope: str = "all",
    company_id: str | None = None,
) -> str:
    status_n = (status or "").strip().lower() or None
    if status_n and status_n not in TRANSFER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status must be draft, requested, in_transit, received, or cancelled",
        )
    rows = await stores_svc.list_transfers_filtered(
        db,
        tenant_id,
        status=status_n,
        store_id=store_id,
        scope=scope or "all",
        limit=500,
        company_id=company_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STOCK_TRANSFER_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await stores_svc.serialize_transfer(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in STOCK_TRANSFER_EXPORT_COLUMNS})
    return buf.getvalue()
