"""CSV export for stores, warehouses, and tax rates (Stage 121 X1)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

STORE_EXPORT_COLUMNS = [
    "code",
    "name",
    "address",
    "phone",
    "manager_id",
    "branch_id",
    "is_active",
]

WAREHOUSE_EXPORT_COLUMNS = [
    "code",
    "name",
    "warehouse_type",
    "store_id",
    "manager_id",
    "address",
    "capacity",
    "is_active",
]

TAX_RATE_EXPORT_COLUMNS = [
    "name",
    "rate",
    "tax_type",
    "pricing_mode",
    "is_reverse_charge",
    "is_default",
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
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def _apply_active_filter(stmt, column, *, is_active: bool | None, active_only: bool):
    if is_active is not None:
        return stmt.where(column.is_(bool(is_active)))
    if active_only:
        return stmt.where(column.is_(True))
    return stmt


async def export_stores_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.Store).where(m.Store.tenant_id == tenant_id)
    stmt = _apply_active_filter(
        stmt, m.Store.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Store.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STORE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "address": _cell(row.address),
                "phone": _cell(row.phone),
                "manager_id": _cell(row.manager_id),
                "branch_id": _cell(row.branch_id),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_warehouses_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.Warehouse).where(m.Warehouse.tenant_id == tenant_id)
    stmt = _apply_active_filter(
        stmt, m.Warehouse.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.Warehouse.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=WAREHOUSE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        capacity = getattr(row, "capacity", None)
        writer.writerow(
            {
                "code": _cell(row.code),
                "name": _cell(row.name),
                "warehouse_type": _cell(getattr(row, "warehouse_type", None) or "retail"),
                "store_id": _cell(row.store_id),
                "manager_id": _cell(getattr(row, "manager_id", None)),
                "address": _cell(getattr(row, "address", None)),
                "capacity": "" if capacity is None else _cell(float(capacity)),
                "is_active": _cell(bool(getattr(row, "is_active", True))),
            }
        )
    return buf.getvalue()


async def export_tax_rates_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.TaxRate).where(m.TaxRate.tenant_id == tenant_id)
    stmt = _apply_active_filter(
        stmt, m.TaxRate.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.TaxRate.name))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TAX_RATE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "name": _cell(row.name),
                "rate": _cell(float(row.rate or 0)),
                "tax_type": _cell(row.tax_type),
                "pricing_mode": _cell(row.pricing_mode),
                "is_reverse_charge": _cell(bool(row.is_reverse_charge)),
                "is_default": _cell(bool(row.is_default)),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()
