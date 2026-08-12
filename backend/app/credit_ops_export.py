"""CSV export for customer/supplier payment registers and credit aging (Stage 136). Header-only."""

from __future__ import annotations

import csv
import io

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import credit as credit_svc
from app import models as m
from app.rbac import apply_created_by_scope
from app.session_passkey_doc_export import _cell

CUSTOMER_PAYMENT_EXPORT_COLUMNS = [
    "payment_number",
    "customer_id",
    "sales_invoice_id",
    "amount",
    "payment_method",
    "early_payment_discount",
    "currency",
    "exchange_rate",
    "fx_gain_loss",
    "liquid_account_id",
    "reference",
    "notes",
    "created_by",
    "created_at",
]

SUPPLIER_PAYMENT_EXPORT_COLUMNS = [
    "payment_number",
    "supplier_id",
    "purchase_order_id",
    "purchase_invoice_id",
    "amount",
    "payment_method",
    "early_payment_discount",
    "currency",
    "exchange_rate",
    "fx_gain_loss",
    "liquid_account_id",
    "reference",
    "notes",
    "created_by",
    "created_at",
]

AGING_EXPORT_COLUMNS = [
    "kind",
    "document_number",
    "party_id",
    "party_name",
    "due_date",
    "balance_due",
    "currency",
    "exchange_rate",
    "balance_due_base",
    "days_overdue",
    "bucket",
]

PAYMENT_METHODS = {"cash", "bank_transfer", "card", "cheque", "mobile_money", "other"}


def serialize_customer_payment(row: m.CustomerPayment) -> dict:
    return {
        "id": row.id,
        "payment_number": row.payment_number,
        "customer_id": row.customer_id,
        "sales_invoice_id": row.sales_invoice_id,
        "amount": float(row.amount or 0),
        "payment_method": row.payment_method,
        "early_payment_discount": float(row.early_payment_discount or 0),
        "currency": row.currency or "",
        "exchange_rate": float(row.exchange_rate or 1),
        "fx_gain_loss": float(row.fx_gain_loss or 0),
        "liquid_account_id": row.liquid_account_id,
        "reference": row.reference,
        "notes": row.notes,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


def serialize_supplier_payment(row: m.SupplierPayment) -> dict:
    return {
        "id": row.id,
        "payment_number": row.payment_number,
        "supplier_id": row.supplier_id,
        "purchase_order_id": row.purchase_order_id,
        "purchase_invoice_id": row.purchase_invoice_id,
        "amount": float(row.amount or 0),
        "payment_method": row.payment_method,
        "early_payment_discount": float(row.early_payment_discount or 0),
        "currency": row.currency or "",
        "exchange_rate": float(row.exchange_rate or 1),
        "fx_gain_loss": float(row.fx_gain_loss or 0),
        "liquid_account_id": row.liquid_account_id,
        "reference": row.reference,
        "notes": row.notes,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


def _normalize_method(payment_method: str | None) -> str | None:
    if not payment_method:
        return None
    key = payment_method.strip().lower()
    if key not in PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail="payment_method must be cash, bank_transfer, card, cheque, mobile_money, or other",
        )
    return key


async def list_customer_payments(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    customer_id: str | None = None,
    payment_method: str | None = None,
    limit: int = 500,
) -> list[m.CustomerPayment]:
    method = _normalize_method(payment_method)
    stmt = (
        select(m.CustomerPayment)
        .where(m.CustomerPayment.tenant_id == tenant_id)
        .order_by(m.CustomerPayment.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if customer_id:
        stmt = stmt.where(m.CustomerPayment.customer_id == customer_id.strip())
    if method:
        stmt = stmt.where(m.CustomerPayment.payment_method == method)
    stmt = apply_created_by_scope(stmt, m.CustomerPayment, claims)
    return list((await db.execute(stmt)).scalars().all())


async def list_supplier_payments(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    supplier_id: str | None = None,
    payment_method: str | None = None,
    limit: int = 500,
) -> list[m.SupplierPayment]:
    method = _normalize_method(payment_method)
    stmt = (
        select(m.SupplierPayment)
        .where(m.SupplierPayment.tenant_id == tenant_id)
        .order_by(m.SupplierPayment.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if supplier_id:
        stmt = stmt.where(m.SupplierPayment.supplier_id == supplier_id.strip())
    if method:
        stmt = stmt.where(m.SupplierPayment.payment_method == method)
    stmt = apply_created_by_scope(stmt, m.SupplierPayment, claims)
    return list((await db.execute(stmt)).scalars().all())


async def export_customer_payments_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    customer_id: str | None = None,
    payment_method: str | None = None,
) -> str:
    rows = await list_customer_payments(
        db,
        tenant_id=tenant_id,
        claims=claims,
        customer_id=customer_id,
        payment_method=payment_method,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CUSTOMER_PAYMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = serialize_customer_payment(row)
        writer.writerow({k: _cell(data.get(k)) for k in CUSTOMER_PAYMENT_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_supplier_payments_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    supplier_id: str | None = None,
    payment_method: str | None = None,
) -> str:
    rows = await list_supplier_payments(
        db,
        tenant_id=tenant_id,
        claims=claims,
        supplier_id=supplier_id,
        payment_method=payment_method,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SUPPLIER_PAYMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = serialize_supplier_payment(row)
        writer.writerow({k: _cell(data.get(k)) for k in SUPPLIER_PAYMENT_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_aging_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    kind: str = "receivable",
) -> str:
    key = (kind or "receivable").strip().lower()
    if key not in {"receivable", "payable"}:
        raise HTTPException(status_code=400, detail="kind must be receivable or payable")
    report = (
        await credit_svc.ap_aging(db, tenant_id)
        if key == "payable"
        else await credit_svc.ar_aging(db, tenant_id)
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=AGING_EXPORT_COLUMNS)
    writer.writeheader()
    for doc in report.get("documents") or []:
        row = {**doc, "kind": key}
        writer.writerow({k: _cell(row.get(k)) for k in AGING_EXPORT_COLUMNS})
    return buf.getvalue()
