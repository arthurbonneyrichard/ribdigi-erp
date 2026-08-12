"""CSV export for customer/supplier payment registers, aging (Stage 136), and party ops (Stage 141)."""

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

OUTSTANDING_EXPORT_COLUMNS = [
    "party_id",
    "party_kind",
    "document_type",
    "document_id",
    "document_number",
    "amount",
    "due_date",
    "status",
]

PAYMENT_SCHEDULE_EXPORT_COLUMNS = [
    "supplier_id",
    "document_type",
    "document_id",
    "document_number",
    "purchase_order_id",
    "amount",
    "due_date",
    "status",
    "days_until_due",
    "is_overdue",
    "schedule_bucket",
    "early_discount_eligible",
    "early_discount_amount",
    "cash_to_settle",
]

STATEMENT_EXPORT_COLUMNS = [
    "party_id",
    "party_name",
    "party_kind",
    "credit_limit",
    "party_balance",
    "date",
    "type",
    "reference",
    "debit",
    "credit",
    "status",
    "balance_due",
]

PAYMENT_METHODS = {"cash", "bank_transfer", "card", "cheque", "mobile_money", "other"}
SCHEDULE_BUCKETS = {"overdue", "due_today", "upcoming", "unscheduled"}


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


async def export_customer_outstanding_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    customer_id: str,
) -> str:
    """Stage 141 O1 — open AR bills CSV for one customer."""
    rows = await credit_svc.customer_outstanding_bills(db, tenant_id, customer_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=OUTSTANDING_EXPORT_COLUMNS)
    writer.writeheader()
    for item in rows:
        writer.writerow(
            {
                "party_id": _cell(customer_id),
                "party_kind": "customer",
                "document_type": _cell(item.get("document_type") or "sales_invoice"),
                "document_id": _cell(item.get("invoice_id")),
                "document_number": _cell(item.get("invoice_number")),
                "amount": _cell(item.get("amount")),
                "due_date": _cell(item.get("due_date")),
                "status": _cell(item.get("status")),
            }
        )
    return buf.getvalue()


async def export_supplier_outstanding_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
) -> str:
    """Stage 141 O1 — open AP bills CSV for one supplier (flat outstanding list)."""
    schedule = await credit_svc.supplier_payment_schedule(db, tenant_id, supplier_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=OUTSTANDING_EXPORT_COLUMNS)
    writer.writeheader()
    for item in schedule.get("items") or []:
        doc_type = item.get("document_type") or ""
        if doc_type == "purchase_invoice":
            doc_id = item.get("purchase_invoice_id")
            doc_num = item.get("invoice_number")
        else:
            doc_id = item.get("purchase_order_id")
            doc_num = item.get("po_number")
        writer.writerow(
            {
                "party_id": _cell(supplier_id),
                "party_kind": "supplier",
                "document_type": _cell(doc_type),
                "document_id": _cell(doc_id),
                "document_number": _cell(doc_num),
                "amount": _cell(item.get("amount")),
                "due_date": _cell(item.get("due_date")),
                "status": _cell(item.get("status")),
            }
        )
    return buf.getvalue()


async def export_supplier_payment_schedule_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
    schedule_bucket: str | None = None,
) -> str:
    """Stage 141 P1 — supplier AP payment schedule CSV with optional bucket filter."""
    bucket = (schedule_bucket or "").strip().lower() or None
    if bucket and bucket not in SCHEDULE_BUCKETS:
        raise HTTPException(
            status_code=400,
            detail="schedule_bucket must be overdue, due_today, upcoming, or unscheduled",
        )
    schedule = await credit_svc.supplier_payment_schedule(db, tenant_id, supplier_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PAYMENT_SCHEDULE_EXPORT_COLUMNS)
    writer.writeheader()
    for item in schedule.get("items") or []:
        if bucket and (item.get("schedule_bucket") or "") != bucket:
            continue
        doc_type = item.get("document_type") or ""
        if doc_type == "purchase_invoice":
            doc_id = item.get("purchase_invoice_id")
            doc_num = item.get("invoice_number")
        else:
            doc_id = item.get("purchase_order_id")
            doc_num = item.get("po_number")
        early = item.get("early_discount") or {}
        writer.writerow(
            {
                "supplier_id": _cell(supplier_id),
                "document_type": _cell(doc_type),
                "document_id": _cell(doc_id),
                "document_number": _cell(doc_num),
                "purchase_order_id": _cell(item.get("purchase_order_id")),
                "amount": _cell(item.get("amount")),
                "due_date": _cell(item.get("due_date")),
                "status": _cell(item.get("status")),
                "days_until_due": _cell(item.get("days_until_due")),
                "is_overdue": _cell(item.get("is_overdue")),
                "schedule_bucket": _cell(item.get("schedule_bucket")),
                "early_discount_eligible": _cell(bool(early.get("eligible"))),
                "early_discount_amount": _cell(early.get("discount_amount")),
                "cash_to_settle": _cell(early.get("cash_to_settle")),
            }
        )
    return buf.getvalue()


async def export_customer_statement_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    customer_id: str,
) -> str:
    """Stage 141 T1 — customer credit statement lines CSV."""
    data = await credit_svc.customer_statement(db, tenant_id, customer_id)
    party = data.get("customer") or {}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STATEMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for line in data.get("lines") or []:
        writer.writerow(
            {
                "party_id": _cell(party.get("id") or customer_id),
                "party_name": _cell(party.get("name")),
                "party_kind": "customer",
                "credit_limit": _cell(party.get("credit_limit")),
                "party_balance": _cell(party.get("balance")),
                "date": _cell(line.get("date")),
                "type": _cell(line.get("type")),
                "reference": _cell(line.get("reference")),
                "debit": _cell(line.get("debit")),
                "credit": _cell(line.get("credit")),
                "status": _cell(line.get("status")),
                "balance_due": _cell(line.get("balance_due")),
            }
        )
    return buf.getvalue()


async def export_supplier_statement_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
) -> str:
    """Stage 141 T1 — supplier credit statement lines CSV."""
    data = await credit_svc.supplier_statement(db, tenant_id, supplier_id)
    party = data.get("supplier") or {}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STATEMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for line in data.get("lines") or []:
        writer.writerow(
            {
                "party_id": _cell(party.get("id") or supplier_id),
                "party_name": _cell(party.get("name")),
                "party_kind": "supplier",
                "credit_limit": "",
                "party_balance": _cell(party.get("balance")),
                "date": _cell(line.get("date")),
                "type": _cell(line.get("type")),
                "reference": _cell(line.get("reference")),
                "debit": _cell(line.get("debit")),
                "credit": _cell(line.get("credit")),
                "status": _cell(line.get("status")),
                "balance_due": _cell(line.get("balance_due")),
            }
        )
    return buf.getvalue()

