"""CSV export for sales quotations, orders, and returns (Stage 133). Header-only."""

from __future__ import annotations

import csv
import io

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import sales_docs as sales_docs_svc
from app.rbac import apply_created_by_scope
from app.session_passkey_doc_export import _cell

QUOTATION_EXPORT_COLUMNS = [
    "quotation_number",
    "customer_id",
    "status",
    "subtotal",
    "tax_amount",
    "discount_amount",
    "total_amount",
    "valid_until",
    "notes",
    "converted_order_id",
    "converted_invoice_id",
    "emailed_at",
    "emailed_to",
    "created_at",
]

ORDER_EXPORT_COLUMNS = [
    "order_number",
    "customer_id",
    "quotation_id",
    "store_id",
    "warehouse_id",
    "status",
    "subtotal",
    "tax_amount",
    "discount_amount",
    "total_amount",
    "delivery_date",
    "delivery_address",
    "converted_invoice_id",
    "reserved_qty_total",
    "confirmed_at",
    "processing_at",
    "shipped_at",
    "delivered_at",
    "created_at",
]

RETURN_EXPORT_COLUMNS = [
    "return_number",
    "credit_note_number",
    "customer_id",
    "sales_invoice_id",
    "status",
    "reason",
    "restock",
    "subtotal",
    "tax_amount",
    "total_amount",
    "notes",
    "posted_at",
    "created_at",
]

QUOTATION_STATUSES = {"draft", "sent", "accepted", "rejected", "expired"}
ORDER_STATUSES = {"draft", "confirmed", "processing", "shipped", "delivered", "cancelled"}
RETURN_STATUSES = {"draft", "posted"}


async def export_quotations_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.SalesQuotation)
        .where(m.SalesQuotation.tenant_id == tenant_id)
        .order_by(m.SalesQuotation.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in QUOTATION_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status must be draft, sent, accepted, rejected, or expired",
            )
        stmt = stmt.where(m.SalesQuotation.status == key)
    stmt = apply_created_by_scope(stmt, m.SalesQuotation, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=QUOTATION_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await sales_docs_svc.serialize_quotation(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in QUOTATION_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_orders_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.SalesOrder)
        .where(m.SalesOrder.tenant_id == tenant_id)
        .order_by(m.SalesOrder.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in ORDER_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status must be draft, confirmed, processing, shipped, delivered, or cancelled",
            )
        stmt = stmt.where(m.SalesOrder.status == key)
    stmt = apply_created_by_scope(stmt, m.SalesOrder, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ORDER_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await sales_docs_svc.serialize_order(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in ORDER_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_returns_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
) -> str:
    stmt = (
        select(m.SalesReturn)
        .where(m.SalesReturn.tenant_id == tenant_id)
        .order_by(m.SalesReturn.created_at.desc())
        .limit(500)
    )
    if status:
        key = status.strip().lower()
        if key not in RETURN_STATUSES:
            raise HTTPException(status_code=400, detail="status must be draft or posted")
        stmt = stmt.where(m.SalesReturn.status == key)
    stmt = apply_created_by_scope(stmt, m.SalesReturn, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=RETURN_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await sales_docs_svc.serialize_return(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in RETURN_EXPORT_COLUMNS})
    return buf.getvalue()
