"""Document number helpers: daily sequences and configurable year series."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import require_honest_narrative
from app.schema_compat import table_column_names

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
# POS/SHIFT prefixes are server-locked; clients cannot choose or rewind the series.
LOCKED_SERIES_PREFIXES = {"pos_sale": "POS", "pos_session": "SHIFT"}

_SEQ_RE = re.compile(r"-(\d+)$")
_PREFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")
SERIES_PAD = 4

# kind -> default prefix + uniqueness model/column (JSON kinds use document_numbering)
SERIES_KINDS: dict[str, dict[str, Any]] = {
    "sales_invoice": {
        "default_prefix": "INV",
        "storage": "columns",
        "model": m.SalesInvoice,
        "field": "invoice_number",
    },
    "quotation": {
        "default_prefix": "QT",
        "storage": "json",
        "model": m.SalesQuotation,
        "field": "quotation_number",
    },
    "purchase_order": {
        "default_prefix": "PO",
        "storage": "json",
        "model": m.PurchaseOrder,
        "field": "po_number",
    },
    "grn": {
        "default_prefix": "GRN",
        "storage": "json",
        "model": m.GoodsReceipt,
        "field": "grn_number",
    },
    "purchase_invoice": {
        "default_prefix": "PINV",
        "storage": "json",
        "model": m.PurchaseInvoice,
        "field": "invoice_number",
    },
    "purchase_return": {
        "default_prefix": "PR",
        "storage": "json",
        "model": m.PurchaseReturn,
        "field": "return_number",
    },
    "debit_note": {
        "default_prefix": "DN",
        "storage": "json",
        "model": m.PurchaseReturn,
        "field": "debit_note_number",
    },
    "sales_return": {
        "default_prefix": "SR",
        "storage": "json",
        "model": m.SalesReturn,
        "field": "return_number",
    },
    "credit_note": {
        "default_prefix": "CN",
        "storage": "json",
        "model": m.SalesReturn,
        "field": "credit_note_number",
    },
    "sales_order": {
        "default_prefix": "SO",
        "storage": "json",
        "model": m.SalesOrder,
        "field": "order_number",
    },
    "purchase_request": {
        "default_prefix": "PREQ",
        "storage": "json",
        "model": m.PurchaseRequest,
        "field": "request_number",
    },
    "customer_payment": {
        "default_prefix": "RCP",
        "storage": "json",
        "model": m.CustomerPayment,
        "field": "payment_number",
    },
    "supplier_payment": {
        "default_prefix": "SPY",
        "storage": "json",
        "model": m.SupplierPayment,
        "field": "payment_number",
    },
    "journal_entry": {
        "default_prefix": "JE",
        "storage": "json",
        "model": m.JournalEntry,
        "field": "entry_number",
    },
    "pos_sale": {
        "default_prefix": "POS",
        "storage": "json",
        "model": m.Transaction,
        "field": "reference",
        "extra_eq": {"tx_type": "pos_sale"},
        # Independent series per company when live tables have company_id.
        "company_scoped": True,
    },
    "pos_session": {
        "default_prefix": "SHIFT",
        "storage": "json",
        "model": m.PosSession,
        "field": "session_number",
        # UniqueConstraint(tenant_id, session_number) — tenant-wide series.
        "company_scoped": False,
    },
    "stock_transfer": {
        "default_prefix": "TR",
        "storage": "json",
        "model": m.StockTransfer,
        "field": "transfer_number",
    },
    "stock_count": {
        "default_prefix": "SC",
        "storage": "json",
        "model": m.StockCount,
        "field": "count_number",
    },
    "expense": {
        "default_prefix": "EXP",
        "storage": "json",
        "model": m.Expense,
        "field": "reference",
    },
    "cash_transfer": {
        "default_prefix": "XFER",
        "storage": "json",
        "model": m.CashTransfer,
        "field": "reference",
    },
    # No dedicated opening-stock table; uniqueness checked on journal reference
    # when a GL entry is posted (audit/response still carry the allocated label).
    "opening_stock": {
        "default_prefix": "OS",
        "storage": "json",
        "model": m.JournalEntry,
        "field": "reference",
    },
}

# Back-compat aliases
DEFAULT_INVOICE_PREFIX = SERIES_KINDS["sales_invoice"]["default_prefix"]
INVOICE_SERIES_PAD = SERIES_PAD


def format_daily_number(prefix: str, day: str | None = None, seq: int = 1) -> str:
    """Build a short number like S260811-001."""
    day_part = day or datetime.utcnow().strftime("%y%m%d")
    return f"{prefix}{day_part}-{max(int(seq), 1):03d}"


def format_series_number(prefix: str, year: int, seq: int, *, pad: int = SERIES_PAD) -> str:
    """Build INV-2026-0001 style series numbers."""
    return f"{prefix}-{int(year)}-{max(int(seq), 1):0{int(pad)}d}"


def normalize_prefix(prefix: str | None, *, default: str = "INV") -> str:
    # OpenAPI DocumentPrefixValue → 422; service defense-in-depth → 400.
    raw = prefix if prefix is not None and str(prefix).strip() else default
    text = require_honest_narrative(
        raw, label="document prefix", max_length=20
    ).strip().upper()
    if not _PREFIX_RE.match(text):
        raise HTTPException(
            status_code=400,
            detail="Document prefix must be 1–20 chars: letters, digits, underscore, or hyphen",
        )
    return text


def normalize_invoice_prefix(prefix: str | None) -> str:
    return normalize_prefix(prefix, default=DEFAULT_INVOICE_PREFIX)


def _json_bucket(tenant: m.Tenant) -> dict:
    raw = getattr(tenant, "document_numbering", None) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _read_state(
    tenant: m.Tenant, kind: str, *, company_id: str | None = None
) -> tuple[str, int, int | None]:
    meta = SERIES_KINDS[kind]
    default_prefix = meta["default_prefix"]
    if meta["storage"] == "columns":
        prefix = getattr(tenant, "sales_invoice_number_prefix", None) or default_prefix
        next_seq = int(getattr(tenant, "sales_invoice_number_next", None) or 1)
        year = getattr(tenant, "sales_invoice_number_year", None)
        return prefix, next_seq, year
    bucket = _json_bucket(tenant).get(kind) or {}
    if not isinstance(bucket, dict):
        bucket = {}
    prefix = bucket.get("prefix") or default_prefix
    next_seq = int(bucket.get("next") or 1)
    year = bucket.get("year")
    if company_id:
        by_co = bucket.get("companies") if isinstance(bucket.get("companies"), dict) else {}
        scoped = by_co.get(company_id) if isinstance(by_co.get(company_id), dict) else {}
        if scoped:
            next_seq = int(scoped.get("next") or next_seq or 1)
            year = scoped.get("year") if scoped.get("year") is not None else year
    return prefix, next_seq, int(year) if year is not None else None


def _write_state(
    tenant: m.Tenant,
    kind: str,
    *,
    prefix: str,
    next_seq: int,
    year: int,
    company_id: str | None = None,
) -> None:
    meta = SERIES_KINDS[kind]
    if meta["storage"] == "columns":
        tenant.sales_invoice_number_prefix = prefix
        tenant.sales_invoice_number_next = next_seq
        tenant.sales_invoice_number_year = year
        return
    data = _json_bucket(tenant)
    bucket = data.get(kind) if isinstance(data.get(kind), dict) else {}
    bucket = dict(bucket)
    bucket["prefix"] = prefix
    bucket["next"] = next_seq
    bucket["year"] = year
    if company_id:
        companies = bucket.get("companies") if isinstance(bucket.get("companies"), dict) else {}
        companies = dict(companies)
        companies[company_id] = {"next": next_seq, "year": year}
        bucket["companies"] = companies
    data[kind] = bucket
    tenant.document_numbering = data


def numbering_settings(tenant: m.Tenant, kind: str, *, as_of: datetime | None = None) -> dict:
    """Serialize numbering config + next preview for one document kind (no side effects)."""
    if kind not in SERIES_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown numbering kind: {kind}")
    now = as_of or datetime.utcnow()
    year = now.year
    locked = LOCKED_SERIES_PREFIXES.get(kind)
    raw_prefix, next_seq, stored_year = _read_state(tenant, kind)
    prefix = locked or normalize_prefix(raw_prefix, default=SERIES_KINDS[kind]["default_prefix"])
    if stored_year is not None and int(stored_year) != year:
        next_seq = 1
    next_seq = max(int(next_seq), 1)
    return {
        "kind": kind,
        "prefix": prefix,
        "next_number": next_seq,
        "year": year,
        "pad": SERIES_PAD,
        "pattern": f"{prefix}-{{YYYY}}-{{NNNN}}",
        "preview": format_series_number(prefix, year, next_seq),
    }


def invoice_numbering_settings(tenant: m.Tenant, *, as_of: datetime | None = None) -> dict:
    return numbering_settings(tenant, "sales_invoice", as_of=as_of)


def all_numbering_settings(tenant: m.Tenant, *, as_of: datetime | None = None) -> dict:
    return {kind: numbering_settings(tenant, kind, as_of=as_of) for kind in SERIES_KINDS}


def apply_numbering_update(
    tenant: m.Tenant,
    kind: str,
    *,
    prefix: str,
    next_number: int,
    as_of: datetime | None = None,
) -> dict:
    if kind not in SERIES_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown numbering kind: {kind}")
    if kind in LOCKED_SERIES_PREFIXES:
        raise HTTPException(
            status_code=400,
            detail="POS and shift numbers are allocated by the server and cannot be set from the client",
        )
    year = (as_of or datetime.utcnow()).year
    clean = normalize_prefix(prefix, default=SERIES_KINDS[kind]["default_prefix"])
    _write_state(tenant, kind, prefix=clean, next_seq=max(int(next_number), 1), year=year)
    return numbering_settings(tenant, kind, as_of=as_of)


def _max_seq(references: list[str], prefix: str) -> int:
    seq = 0
    for ref in references:
        text = str(ref or "")
        if not text.startswith(prefix):
            continue
        match = _SEQ_RE.search(text)
        if not match:
            continue
        try:
            seq = max(seq, int(match.group(1)))
        except ValueError:
            continue
    return seq


async def next_daily_number(
    db: AsyncSession,
    *,
    tenant_id: str,
    prefix: str,
    references: list[str],
) -> str:
    day = datetime.utcnow().strftime("%y%m%d")
    full_prefix = f"{prefix}{day}-"
    seq = _max_seq(references, full_prefix) + 1
    return format_daily_number(prefix, day, seq)


async def resolve_pos_company_id(
    db: AsyncSession, tenant_id: str, store_id: str | None = None
) -> str | None:
    """Company for POS numbering: store.company_id when present, else tenant default."""
    if store_id and _IDENT.match(store_id):
        cols = await table_column_names(db, "stores")
        if "company_id" in cols:
            row = (
                await db.execute(
                    text(
                        "SELECT company_id FROM stores WHERE id = :sid AND tenant_id = :tid"
                    ),
                    {"sid": store_id, "tid": tenant_id},
                )
            ).first()
            if row and row[0]:
                return str(row[0])
    from app.schema_compat import resolve_tenant_company_id

    return await resolve_tenant_company_id(db, tenant_id)


async def next_pos_sale_number(
    db: AsyncSession, tenant_id: str, *, company_id: str | None = None
) -> str:
    """Allocate next POS sale reference (POS-YYYY-NNNN) for this tenant/company."""
    return await next_series_document_number(
        db, tenant_id, "pos_sale", company_id=company_id
    )


async def next_pos_session_number(
    db: AsyncSession, tenant_id: str, *, company_id: str | None = None
) -> str:
    """Allocate next POS shift session number (SHIFT-YYYY-NNNN). Unique per tenant."""
    return await next_series_document_number(
        db, tenant_id, "pos_session", company_id=company_id
    )


async def next_stock_transfer_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "stock_transfer")


async def next_stock_count_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "stock_count")


async def next_expense_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "expense")


async def next_cash_transfer_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "cash_transfer")


async def next_opening_stock_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "opening_stock")


async def _resolve_series_company_id(
    db: AsyncSession, tenant_id: str, kind: str, company_id: str | None
) -> str | None:
    meta = SERIES_KINDS[kind]
    if not meta.get("company_scoped"):
        return None
    table = meta["model"].__tablename__
    if not _IDENT.match(table):
        return None
    cols = await table_column_names(db, table)
    if "company_id" not in cols:
        return None
    if company_id:
        return company_id
    from app.schema_compat import resolve_tenant_company_id

    return await resolve_tenant_company_id(db, tenant_id)


async def _series_values(
    db: AsyncSession,
    *,
    table: str,
    column: str,
    tenant_id: str,
    like_prefix: str,
    company_id: str | None,
    extra_eq: dict[str, Any] | None,
) -> list[str]:
    if not _IDENT.match(table) or not _IDENT.match(column):
        raise HTTPException(status_code=500, detail="Invalid numbering target")
    cols = await table_column_names(db, table)
    if not cols or column not in cols or "tenant_id" not in cols:
        return []
    clauses = ["tenant_id = :tid", f"{column} LIKE :pat"]
    params: dict[str, Any] = {"tid": tenant_id, "pat": f"{like_prefix}%"}
    if extra_eq:
        for key, value in extra_eq.items():
            if key in cols and _IDENT.match(key):
                clauses.append(f"{key} = :{key}")
                params[key] = value
    if company_id and "company_id" in cols:
        clauses.append("company_id = :cid")
        params["cid"] = company_id
    rows = (
        await db.execute(
            text(f"SELECT {column} FROM {table} WHERE {' AND '.join(clauses)}"),
            params,
        )
    ).scalars().all()
    return [str(v) for v in rows if v is not None]


async def _series_taken(
    db: AsyncSession,
    *,
    table: str,
    column: str,
    tenant_id: str,
    candidate: str,
    company_id: str | None,
    extra_eq: dict[str, Any] | None,
) -> bool:
    if not _IDENT.match(table) or not _IDENT.match(column):
        raise HTTPException(status_code=500, detail="Invalid numbering target")
    cols = await table_column_names(db, table)
    if not cols or column not in cols or "tenant_id" not in cols:
        return False
    clauses = ["tenant_id = :tid", f"{column} = :num"]
    params: dict[str, Any] = {"tid": tenant_id, "num": candidate}
    if extra_eq:
        for key, value in extra_eq.items():
            if key in cols and _IDENT.match(key):
                clauses.append(f"{key} = :{key}")
                params[key] = value
    if company_id and "company_id" in cols:
        clauses.append("company_id = :cid")
        params["cid"] = company_id
    found = (
        await db.execute(
            text(f"SELECT 1 FROM {table} WHERE {' AND '.join(clauses)} LIMIT 1"),
            params,
        )
    ).first()
    return found is not None


async def next_series_document_number(
    db: AsyncSession,
    tenant_id: str,
    kind: str,
    *,
    company_id: str | None = None,
) -> str:
    """Allocate next `{prefix}-{YYYY}-{NNNN}` for the given document kind.

    POS/SHIFT prefixes are locked. Sequence is advanced under a tenant row lock
    and skips numbers that already exist so historic documents are preserved.
    """
    if kind not in SERIES_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown numbering kind: {kind}")
    meta = SERIES_KINDS[kind]
    model = meta["model"]
    field_name = meta["field"]
    table = model.__tablename__
    extra_eq = meta.get("extra_eq") if isinstance(meta.get("extra_eq"), dict) else None

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())
    ).scalar_one()
    year = datetime.utcnow().year
    scope_company = await _resolve_series_company_id(db, tenant_id, kind, company_id)
    raw_prefix, next_seq, stored_year = _read_state(tenant, kind, company_id=scope_company)
    prefix = LOCKED_SERIES_PREFIXES.get(kind) or normalize_prefix(
        raw_prefix, default=meta["default_prefix"]
    )
    if stored_year is None or int(stored_year) != year:
        next_seq = 1
        stored_year = year

    like_prefix = f"{prefix}-{year}-"
    existing_max = _max_seq(
        await _series_values(
            db,
            table=table,
            column=field_name,
            tenant_id=tenant_id,
            like_prefix=like_prefix,
            company_id=scope_company,
            extra_eq=extra_eq,
        ),
        like_prefix,
    )
    next_seq = max(int(next_seq), existing_max + 1, 1)

    for _ in range(10_000):
        seq = max(int(next_seq), 1)
        candidate = format_series_number(prefix, year, seq)
        next_seq = seq + 1
        _write_state(
            tenant,
            kind,
            prefix=prefix,
            next_seq=next_seq,
            year=year,
            company_id=scope_company,
        )
        taken = await _series_taken(
            db,
            table=table,
            column=field_name,
            tenant_id=tenant_id,
            candidate=candidate,
            company_id=scope_company,
            extra_eq=extra_eq,
        )
        if not taken:
            await db.flush()
            return candidate

    raise HTTPException(status_code=500, detail=f"Unable to allocate {kind} number")


async def next_sales_invoice_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "sales_invoice")


async def next_quotation_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "quotation")


async def next_purchase_order_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "purchase_order")


async def next_grn_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "grn")


async def next_purchase_invoice_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "purchase_invoice")


async def next_purchase_return_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "purchase_return")


async def next_debit_note_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "debit_note")


async def next_sales_return_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "sales_return")


async def next_credit_note_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "credit_note")


async def next_sales_order_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "sales_order")


async def next_purchase_request_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "purchase_request")


async def next_customer_payment_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "customer_payment")


async def next_supplier_payment_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "supplier_payment")


async def next_journal_entry_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "journal_entry")
