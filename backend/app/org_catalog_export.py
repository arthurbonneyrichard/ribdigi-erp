"""CSV export for branches, departments, and catalog meta (Stage 122 X1)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

BRANCH_EXPORT_COLUMNS = [
    "company_id",
    "code",
    "name",
    "address",
    "phone",
    "email",
    "manager_id",
    "is_active",
]

DEPARTMENT_EXPORT_COLUMNS = [
    "company_id",
    "code",
    "name",
    "branch_id",
    "head_user_id",
    "is_active",
]

CATEGORY_EXPORT_COLUMNS = [
    "code",
    "name",
    "parent_id",
    "tax_rate_id",
    "is_active",
]

BRAND_EXPORT_COLUMNS = [
    "code",
    "name",
    "description",
    "is_active",
]

UNIT_EXPORT_COLUMNS = [
    "code",
    "name",
    "base_unit_id",
    "conversion_factor",
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
        return f"{value:.6f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def _apply_active_filter(stmt, column, *, is_active: bool | None, active_only: bool):
    if is_active is not None:
        return stmt.where(column.is_(bool(is_active)))
    if active_only:
        return stmt.where(column.is_(True))
    return stmt


async def export_branches_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.Branch).where(m.Branch.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Branch.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.Branch.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Branch.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BRANCH_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "company_id": _cell(getattr(row, "company_id", None)),
                "code": _cell(row.code),
                "name": _cell(row.name),
                "address": _cell(row.address),
                "phone": _cell(getattr(row, "phone", None)),
                "email": _cell(getattr(row, "email", None)),
                "manager_id": _cell(getattr(row, "manager_id", None)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_departments_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    branch_id: str | None = None,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.Department).where(m.Department.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Department.company_id == company_id)
    if branch_id:
        stmt = stmt.where(m.Department.branch_id == branch_id)
    stmt = _apply_active_filter(
        stmt, m.Department.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Department.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DEPARTMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "company_id": _cell(getattr(row, "company_id", None)),
                "code": _cell(row.code),
                "name": _cell(row.name),
                "branch_id": _cell(row.branch_id),
                "head_user_id": _cell(getattr(row, "head_user_id", None)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_categories_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.ProductCategory.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.ProductCategory.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.ProductCategory.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CATEGORY_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "parent_id": _cell(row.parent_id),
                "tax_rate_id": _cell(getattr(row, "tax_rate_id", None)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_brands_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.Brand).where(m.Brand.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Brand.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.Brand.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Brand.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BRAND_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "description": _cell(row.description),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_units_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
    company_id: str | None = None,
) -> str:
    stmt = select(m.UnitOfMeasure).where(m.UnitOfMeasure.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.UnitOfMeasure.company_id == company_id)
    stmt = _apply_active_filter(
        stmt, m.UnitOfMeasure.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.UnitOfMeasure.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=UNIT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "base_unit_id": _cell(getattr(row, "base_unit_id", None)),
                "conversion_factor": _cell(float(getattr(row, "conversion_factor", 1) or 1)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()
