"""CSV export for journals, bank statements, email (Stage 131), SMS (Stage 135), account ledger & fiscal (Stage 139). Secrets excluded."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import accounting as accounting_svc
from app import bank_recon as bank_recon_svc
from app import emailer
from app import sms as sms_svc
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

SMS_SETTINGS_EXPORT_COLUMNS = [
    "enabled",
    "configured",
    "mode",
    "from_number",
    "account_sid_set",
]

ACCOUNT_TX_EXPORT_COLUMNS = [
    "account_code",
    "account_name",
    "entry_date",
    "entry_number",
    "reference",
    "description",
    "source_type",
    "source_id",
    "status",
    "debit",
    "credit",
    "balance",
]

FISCAL_PERIOD_EXPORT_COLUMNS = [
    "fiscal_year_start",
    "open_period_start",
    "open_period_end_exclusive",
    "current_period_closed",
    "closed_period_starts",
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


def export_sms_settings_csv() -> str:
    """Stage 135 S1 — SMS status CSV; never include Twilio auth token or raw SID."""
    data = sms_svc.sms_status()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SMS_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in SMS_SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_account_transactions_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    include_unposted: bool = False,
) -> str:
    """Stage 139 A1 — COA account ledger lines CSV."""
    data = await accounting_svc.account_transactions(
        db,
        tenant_id,
        account_id,
        from_date=from_date,
        to_date=to_date,
        include_unposted=include_unposted,
    )
    account = data.get("account") or {}
    code = account.get("code")
    name = account.get("name")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ACCOUNT_TX_EXPORT_COLUMNS)
    writer.writeheader()
    for row in data.get("transactions") or []:
        writer.writerow(
            {
                "account_code": _cell(code),
                "account_name": _cell(name),
                "entry_date": _cell(row.get("entry_date")),
                "entry_number": _cell(row.get("entry_number")),
                "reference": _cell(row.get("reference")),
                "description": _cell(row.get("description")),
                "source_type": _cell(row.get("source_type")),
                "source_id": _cell(row.get("source_id")),
                "status": _cell(row.get("status")),
                "debit": _cell(row.get("debit")),
                "credit": _cell(row.get("credit")),
                "balance": _cell(row.get("balance")),
            }
        )
    return buf.getvalue()


async def export_fiscal_period_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    """Stage 139 F1 — fiscal period status CSV (singleton row)."""
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    data = accounting_svc.serialize_fiscal_period_status(tenant)
    row = {
        "fiscal_year_start": data.get("fiscal_year_start"),
        "open_period_start": data.get("open_period_start"),
        "open_period_end_exclusive": data.get("open_period_end_exclusive"),
        "current_period_closed": data.get("current_period_closed"),
        "closed_period_starts": json.dumps(
            data.get("closed_period_starts") or [], separators=(",", ":"), default=str
        ),
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FISCAL_PERIOD_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(row.get(k)) for k in FISCAL_PERIOD_EXPORT_COLUMNS})
    return buf.getvalue()


TRIAL_BALANCE_EXPORT_COLUMNS = [
    "as_of",
    "account_id",
    "code",
    "name",
    "account_type",
    "debit",
    "credit",
    "balance",
    "total_debit",
    "total_credit",
    "balanced",
]


async def export_trial_balance_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    as_of=None,
) -> str:
    """Stage 159 B1 — accounting trial-balance CSV (path-scoped; distinct from reports/export)."""
    from app.accounting import ensure_default_accounts, trial_balance

    await ensure_default_accounts(db, tenant_id)
    data = await trial_balance(db, tenant_id, as_of=as_of)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TRIAL_BALANCE_EXPORT_COLUMNS)
    writer.writeheader()
    as_of_v = data.get("as_of")
    total_debit = data.get("total_debit")
    total_credit = data.get("total_credit")
    balanced = data.get("balanced")
    rows = data.get("rows") or []
    if not rows:
        writer.writerow(
            {
                "as_of": _cell(as_of_v),
                "account_id": "",
                "code": "",
                "name": "",
                "account_type": "",
                "debit": "",
                "credit": "",
                "balance": "",
                "total_debit": _cell(total_debit),
                "total_credit": _cell(total_credit),
                "balanced": _cell(balanced),
            }
        )
        return buf.getvalue()
    for row in rows:
        writer.writerow(
            {
                "as_of": _cell(as_of_v),
                "account_id": _cell(row.get("account_id")),
                "code": _cell(row.get("code")),
                "name": _cell(row.get("name")),
                "account_type": _cell(row.get("account_type")),
                "debit": _cell(row.get("debit")),
                "credit": _cell(row.get("credit")),
                "balance": _cell(row.get("balance")),
                "total_debit": _cell(total_debit),
                "total_credit": _cell(total_credit),
                "balanced": _cell(balanced),
            }
        )
    return buf.getvalue()
