"""CSV export for journals, bank statements, and email settings (Stage 131). Secrets excluded."""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import accounting as accounting_svc
from app import bank_recon as bank_recon_svc
from app import emailer
from app import tenants as tenants_svc
from app.session_passkey_doc_export import _cell

JOURNAL_EXPORT_COLUMNS = [
    "entry_number",
    "entry_date",
    "status",
    "reference",
    "description",
    "source_type",
    "source_id",
    "store_id",
    "total_debit",
    "total_credit",
    "balanced",
    "has_attachment",
    "created_by",
    "created_at",
]

BANK_STATEMENT_EXPORT_COLUMNS = [
    "id",
    "account_id",
    "statement_date",
    "status",
    "opening_balance",
    "closing_balance",
    "line_count",
    "matched_count",
    "unmatched_count",
    "ignored_count",
    "notes",
    "reconciled_at",
    "created_by",
    "created_at",
]

EMAIL_SETTINGS_EXPORT_COLUMNS = [
    "enabled",
    "configured",
    "mode",
    "source",
    "host",
    "port",
    "from_email",
    "from_name",
    "use_tls",
    "use_ssl",
    "username",
    "has_password",
    "tenant_override_enabled",
    "frontend_url",
]


async def list_journals(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    store_id: str | None = None,
    limit: int = 100,
) -> list[m.JournalEntry]:
    stmt = (
        select(m.JournalEntry)
        .where(m.JournalEntry.tenant_id == tenant_id)
        .order_by(m.JournalEntry.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if store_id:
        stmt = stmt.where(m.JournalEntry.store_id == store_id)
    status_n = (status or "").strip().lower() or None
    if status_n and status_n != "all":
        stmt = stmt.where(m.JournalEntry.status == status_n)
    return list((await db.execute(stmt)).scalars().all())


async def export_journals_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    store_id: str | None = None,
) -> str:
    rows = await list_journals(
        db, tenant_id=tenant_id, status=status, store_id=store_id, limit=200
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=JOURNAL_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await accounting_svc.serialize_journal(db, row)
        writer.writerow({k: _cell(data.get(k)) for k in JOURNAL_EXPORT_COLUMNS})
    return buf.getvalue()


async def list_bank_statements(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
) -> list[m.BankStatement]:
    q = select(m.BankStatement).where(m.BankStatement.tenant_id == tenant_id)
    status_n = (status or "").strip().lower() or None
    if status_n:
        q = q.where(m.BankStatement.status == status_n)
    q = q.order_by(m.BankStatement.created_at.desc())
    return list((await db.execute(q)).scalars().all())


async def export_bank_statements_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
) -> str:
    rows = await list_bank_statements(db, tenant_id=tenant_id, status=status)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BANK_STATEMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        lines = await bank_recon_svc.list_statement_lines(db, tenant_id, row.id)
        data = bank_recon_svc.serialize_statement(row, lines)
        writer.writerow({k: _cell(data.get(k)) for k in BANK_STATEMENT_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_email_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    data = emailer.email_status(tenant)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EMAIL_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in EMAIL_SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()
