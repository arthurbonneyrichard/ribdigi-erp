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
    company_id: str | None = None,
    limit: int = 100,
) -> list[m.JournalEntry]:
    stmt = (
        select(m.JournalEntry)
        .where(m.JournalEntry.tenant_id == tenant_id)
        .order_by(m.JournalEntry.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if company_id:
        stmt = stmt.where(m.JournalEntry.company_id == company_id)
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
    company_id: str | None = None,
) -> str:
    rows = await list_journals(
        db,
        tenant_id=tenant_id,
        status=status,
        store_id=store_id,
        company_id=company_id,
        limit=200,
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
    company_id: str | None = None,
) -> list[m.BankStatement]:
    q = select(m.BankStatement).where(m.BankStatement.tenant_id == tenant_id)
    if company_id:
        q = q.where(m.BankStatement.company_id == company_id)
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
    company_id: str | None = None,
) -> str:
    rows = await list_bank_statements(
        db, tenant_id=tenant_id, status=status, company_id=company_id
    )
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
    company_id: str | None = None,
) -> str:
    """Stage 139 A1 — COA account ledger lines CSV."""
    data = await accounting_svc.account_transactions(
        db,
        tenant_id,
        account_id,
        from_date=from_date,
        to_date=to_date,
        include_unposted=include_unposted,
        company_id=company_id,
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
    company_id: str | None = None,
) -> str:
    """Stage 159 B1 — accounting trial-balance CSV (path-scoped; distinct from reports/export)."""
    from app.accounting import ensure_default_accounts, trial_balance

    await ensure_default_accounts(db, tenant_id, company_id=company_id)
    data = await trial_balance(db, tenant_id, as_of=as_of, company_id=company_id)
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


PROFIT_LOSS_EXPORT_COLUMNS = [
    "from_date",
    "to_date",
    "store_id",
    "branch_id",
    "account_id",
    "code",
    "name",
    "account_type",
    "bucket",
    "balance",
    "revenue",
    "other_income",
    "cogs",
    "gross_profit",
    "operating_expenses",
    "income",
    "expense",
    "net_profit",
]


async def export_profit_loss_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date=None,
    to_date=None,
    store_id: str | None = None,
    branch_id: str | None = None,
    company_id: str | None = None,
) -> str:
    """Stage 160 P1 — accounting profit-loss CSV (path-scoped; distinct from reports/export)."""
    from app.accounting import ensure_default_accounts, profit_and_loss

    await ensure_default_accounts(db, tenant_id, company_id=company_id)
    data = await profit_and_loss(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        branch_id=branch_id,
        company_id=company_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PROFIT_LOSS_EXPORT_COLUMNS)
    writer.writeheader()
    summary = {
        "from_date": _cell(data.get("from_date")),
        "to_date": _cell(data.get("to_date")),
        "store_id": _cell(data.get("store_id")),
        "branch_id": _cell(data.get("branch_id")),
        "revenue": _cell(data.get("revenue")),
        "other_income": _cell(data.get("other_income")),
        "cogs": _cell(data.get("cogs")),
        "gross_profit": _cell(data.get("gross_profit")),
        "operating_expenses": _cell(data.get("operating_expenses")),
        "income": _cell(data.get("income")),
        "expense": _cell(data.get("expense")),
        "net_profit": _cell(data.get("net_profit")),
    }
    accounts = data.get("accounts") or []
    if not accounts:
        writer.writerow(
            {
                **summary,
                "account_id": "",
                "code": "",
                "name": "",
                "account_type": "",
                "bucket": "",
                "balance": "",
            }
        )
        return buf.getvalue()
    for row in accounts:
        writer.writerow(
            {
                **summary,
                "account_id": _cell(row.get("account_id")),
                "code": _cell(row.get("code")),
                "name": _cell(row.get("name")),
                "account_type": _cell(row.get("account_type")),
                "bucket": _cell(row.get("bucket")),
                "balance": _cell(row.get("balance")),
            }
        )
    return buf.getvalue()


CASH_FLOW_EXPORT_COLUMNS = [
    "from_date",
    "to_date",
    "store_id",
    "branch_id",
    "date",
    "entry_number",
    "description",
    "account_code",
    "account_name",
    "activity",
    "source_type",
    "inflow",
    "outflow",
    "opening_cash",
    "closing_cash",
    "net_change",
    "operating_net",
    "investing_net",
    "financing_net",
]


async def export_cash_flow_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date=None,
    to_date=None,
    store_id: str | None = None,
    branch_id: str | None = None,
    company_id: str | None = None,
) -> str:
    """Stage 160 C1 — reports cash-flow path CSV (distinct from generic /reports/export)."""
    from app import reports as reports_svc

    data = await reports_svc.cash_flow(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        branch_id=branch_id,
        company_id=company_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CASH_FLOW_EXPORT_COLUMNS)
    writer.writeheader()
    summary = {
        "from_date": _cell(data.get("from_date")),
        "to_date": _cell(data.get("to_date")),
        "store_id": _cell(data.get("store_id")),
        "branch_id": _cell(data.get("branch_id")),
        "opening_cash": _cell(data.get("opening_cash")),
        "closing_cash": _cell(data.get("closing_cash")),
        "net_change": _cell(data.get("net_change")),
        "operating_net": _cell((data.get("operating") or {}).get("net")),
        "investing_net": _cell((data.get("investing") or {}).get("net")),
        "financing_net": _cell((data.get("financing") or {}).get("net")),
    }
    lines = data.get("lines") or []
    if not lines:
        writer.writerow(
            {
                **summary,
                "date": "",
                "entry_number": "",
                "description": "",
                "account_code": "",
                "account_name": "",
                "activity": "",
                "source_type": "",
                "inflow": "",
                "outflow": "",
            }
        )
        return buf.getvalue()
    for row in lines:
        writer.writerow(
            {
                **summary,
                "date": _cell(row.get("date")),
                "entry_number": _cell(row.get("entry_number")),
                "description": _cell(row.get("description")),
                "account_code": _cell(row.get("account_code")),
                "account_name": _cell(row.get("account_name")),
                "activity": _cell(row.get("activity")),
                "source_type": _cell(row.get("source_type")),
                "inflow": _cell(row.get("inflow")),
                "outflow": _cell(row.get("outflow")),
            }
        )
    return buf.getvalue()


BALANCE_SHEET_EXPORT_COLUMNS = [
    "as_of",
    "store_id",
    "branch_id",
    "section",
    "code",
    "name",
    "balance",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "total_liabilities_and_equity",
    "balanced",
]


async def export_balance_sheet_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    as_of=None,
    store_id: str | None = None,
    branch_id: str | None = None,
    company_id: str | None = None,
) -> str:
    """Stage 160 S1 — reports balance-sheet path CSV (distinct from generic /reports/export)."""
    from app import reports as reports_svc

    data = await reports_svc.balance_sheet(
        db,
        tenant_id,
        as_of=as_of,
        store_id=store_id,
        branch_id=branch_id,
        company_id=company_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BALANCE_SHEET_EXPORT_COLUMNS)
    writer.writeheader()
    summary = {
        "as_of": _cell(data.get("as_of")),
        "store_id": _cell(data.get("store_id")),
        "branch_id": _cell(data.get("branch_id")),
        "total_assets": _cell(data.get("total_assets")),
        "total_liabilities": _cell(data.get("total_liabilities")),
        "total_equity": _cell(data.get("total_equity")),
        "total_liabilities_and_equity": _cell(data.get("total_liabilities_and_equity")),
        "balanced": _cell(data.get("balanced")),
    }
    rows: list[tuple[str, dict]] = []
    for section in ("assets", "liabilities", "equity"):
        for row in data.get(section) or []:
            rows.append((section, row))
    if not rows:
        writer.writerow({**summary, "section": "", "code": "", "name": "", "balance": ""})
        return buf.getvalue()
    for section, row in rows:
        writer.writerow(
            {
                **summary,
                "section": section,
                "code": _cell(row.get("code")),
                "name": _cell(row.get("name")),
                "balance": _cell(row.get("balance")),
            }
        )
    return buf.getvalue()


TAX_REPORT_EXPORT_COLUMNS = [
    "from_date",
    "to_date",
    "period",
    "period_year",
    "period_month",
    "period_quarter",
    "output_tax",
    "output_tax_invoices",
    "output_tax_pos",
    "reverse_charge_tax",
    "input_tax",
    "input_tax_source",
    "net_tax_payable",
    "invoice_count",
    "pos_sale_count",
    "purchase_count",
    "purchase_order_count",
    "taxable_outputs_net",
    "zero_rated_outputs_net",
    "exempt_outputs_net",
    "taxable_inputs_net",
]


async def export_tax_report_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date=None,
    to_date=None,
    period: str | None = None,
    year: int | None = None,
    month: int | None = None,
    quarter: int | None = None,
) -> str:
    """Stage 161 X1 — reports tax path CSV (distinct from generic /reports/export)."""
    from app import reports as reports_svc
    from app import tax as tax_svc

    fd, td, meta = reports_svc.resolve_report_period(
        period=period,
        year=year,
        month=month,
        quarter=quarter,
        from_date=from_date,
        to_date=to_date,
    )
    data = await tax_svc.tax_report(
        db,
        tenant_id,
        from_date=fd,
        to_date=td,
    )
    data["period"] = meta.get("period")
    data["period_year"] = meta.get("year")
    data["period_month"] = meta.get("month")
    data["period_quarter"] = meta.get("quarter")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TAX_REPORT_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in TAX_REPORT_EXPORT_COLUMNS})
    return buf.getvalue()
