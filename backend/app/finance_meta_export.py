"""CSV export for COA accounts, expense categories, and customer groups (Stage 123 X1)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

ACCOUNT_EXPORT_COLUMNS = [
    "code",
    "name",
    "account_type",
    "parent_id",
    "is_cash_account",
    "is_bank_account",
    "is_system",
    "is_active",
]

EXPENSE_CATEGORY_EXPORT_COLUMNS = [
    "code",
    "name",
    "budget_amount",
    "account_id",
    "is_active",
]

CUSTOMER_GROUP_EXPORT_COLUMNS = [
    "name",
    "discount_percent",
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


async def export_accounts_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.Account).where(m.Account.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Account.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.Account.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Account.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ACCOUNT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "account_type": _cell(row.account_type),
                "parent_id": _cell(row.parent_id),
                "is_cash_account": _cell(bool(row.is_cash_account)),
                "is_bank_account": _cell(bool(row.is_bank_account)),
                "is_system": _cell(bool(getattr(row, "is_system", False))),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_expense_categories_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.ExpenseCategory.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.ExpenseCategory.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.ExpenseCategory.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPENSE_CATEGORY_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "budget_amount": _cell(float(row.budget_amount or 0)),
                "account_id": _cell(row.account_id),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_customer_groups_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.CustomerGroup).where(m.CustomerGroup.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.CustomerGroup.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.CustomerGroup.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.CustomerGroup.name))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CUSTOMER_GROUP_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "name": _cell(row.name),
                "discount_percent": _cell(float(row.discount_percent or 0)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()
