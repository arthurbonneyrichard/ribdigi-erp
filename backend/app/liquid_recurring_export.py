"""CSV export for liquid accounts and recurring expenses (Stage 125 X1)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

LIQUID_EXPORT_COLUMNS = [
    "code",
    "name",
    "kind",
    "bank_name",
    "account_number",
    "bank_branch",
    "balance",
    "is_active",
]

RECURRING_EXPORT_COLUMNS = [
    "category",
    "description",
    "amount",
    "frequency",
    "payment_method",
    "payee",
    "store_id",
    "department_id",
    "next_run_at",
    "is_active",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def _apply_active_filter(stmt, column, *, is_active: bool | None, active_only: bool):
    if is_active is not None:
        return stmt.where(column.is_(bool(is_active)))
    if active_only:
        return stmt.where(column.is_(True))
    return stmt


async def export_liquid_accounts_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.Account).where(
        m.Account.tenant_id == tenant_id,
        or_(m.Account.is_cash_account.is_(True), m.Account.is_bank_account.is_(True)),
    )
    stmt = _apply_active_filter(
        stmt, m.Account.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Account.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LIQUID_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        kind = "cash" if row.is_cash_account else "bank" if row.is_bank_account else ""
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "kind": _cell(kind),
                "bank_name": _cell(row.bank_name),
                "account_number": _cell(row.account_number),
                "bank_branch": _cell(row.bank_branch),
                "balance": _cell(float(row.balance or 0)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_recurring_expenses_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.RecurringExpense).where(m.RecurringExpense.tenant_id == tenant_id)
    stmt = _apply_active_filter(
        stmt, m.RecurringExpense.is_active, is_active=is_active, active_only=active_only
    )
    rows = (
        await db.execute(stmt.order_by(m.RecurringExpense.created_at.desc()))
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=RECURRING_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "category": _cell(row.category),
                "description": _cell(row.description),
                "amount": _cell(float(row.amount or 0)),
                "frequency": _cell(row.frequency),
                "payment_method": _cell(row.payment_method),
                "payee": _cell(row.payee),
                "store_id": _cell(getattr(row, "store_id", None)),
                "department_id": _cell(getattr(row, "department_id", None)),
                "next_run_at": _cell(row.next_run_at),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()
