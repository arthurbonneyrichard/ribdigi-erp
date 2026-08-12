"""CSV export for expenses (Stage 120 X1)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import apply_created_by_scope

EXPENSE_EXPORT_COLUMNS = [
    "expense_date",
    "category",
    "payee",
    "description",
    "amount",
    "payment_method",
    "reference",
    "status",
    "store_id",
    "department_id",
    "created_by",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


async def export_expenses_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    claims: dict,
    status: str | None = None,
    store_id: str | None = None,
    department_id: str | None = None,
) -> str:
    """Stage 120 X1 — export tenant expenses (record-scope aware)."""
    stmt = (
        select(m.Expense)
        .where(m.Expense.tenant_id == tenant_id)
        .order_by(m.Expense.created_at.desc())
    )
    if store_id:
        stmt = stmt.where(m.Expense.store_id == store_id)
    if department_id:
        stmt = stmt.where(m.Expense.department_id == department_id)
    if status:
        key = status.strip().lower()
        if key not in {"pending", "approved", "rejected"}:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail="status must be pending, approved, or rejected",
            )
        stmt = stmt.where(m.Expense.status == key)
    stmt = apply_created_by_scope(stmt, m.Expense, claims)
    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPENSE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "expense_date": _cell(row.expense_date),
                "category": _cell(row.category),
                "payee": _cell(row.payee),
                "description": _cell(row.description),
                "amount": _cell(float(row.amount or 0)),
                "payment_method": _cell(row.payment_method),
                "reference": _cell(row.reference),
                "status": _cell(row.status),
                "store_id": _cell(row.store_id),
                "department_id": _cell(getattr(row, "department_id", None)),
                "created_by": _cell(row.created_by),
            }
        )
    return buf.getvalue()
