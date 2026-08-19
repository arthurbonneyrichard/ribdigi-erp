"""CSV export for stores, warehouses, tax rates (Stage 121 X1), drawer settings (Stage 142 C1),
and store inventory / sales (Stage 155 I1 / S1)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cash_drawer as cash_drawer_svc
from app import models as m
from app import stores as stores_svc

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

DRAWER_SETTINGS_EXPORT_COLUMNS = [
    "store_id",
    "code",
    "name",
    "drawer_mode",
    "drawer_host",
    "drawer_port",
    "drawer_open_on_cash",
    "is_active",
]

STORE_INVENTORY_EXPORT_COLUMNS = [
    "store_id",
    "warehouse_id",
    "product_id",
    "sku",
    "name",
    "quantity",
    "reorder_level",
    "reorder_qty",
    "below_reorder",
    "suggested_order_qty",
    "consolidated_stock",
]

STORE_SALES_EXPORT_COLUMNS = [
    "store_id",
    "store_code",
    "store_name",
    "row_type",
    "source",
    "record_id",
    "number",
    "total",
    "tax",
    "status",
    "occurred_at",
    "invoice_count",
    "pos_count",
    "sale_count",
    "revenue",
    "avg_ticket",
    "from_date",
    "to_date",
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
    company_id: str | None = None,
) -> str:
    stmt = select(m.Store).where(m.Store.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Store.company_id == company_id)
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
    company_id: str | None = None,
) -> str:
    stmt = select(m.Warehouse).where(m.Warehouse.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Warehouse.company_id == company_id)
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
    company_id: str | None = None,
) -> str:
    stmt = select(m.TaxRate).where(m.TaxRate.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.TaxRate.company_id == company_id)
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


async def export_drawer_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    company_id: str | None = None,
) -> str:
    """Stage 142 C1 — secret-free cash drawer settings (kick bytes never included)."""
    stmt = select(m.Store).where(m.Store.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Store.company_id == company_id)
    if is_active is not None:
        stmt = stmt.where(m.Store.is_active.is_(bool(is_active)))
    rows = (await db.execute(stmt.order_by(m.Store.code))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DRAWER_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        cfg = cash_drawer_svc.serialize_drawer_settings(row)
        writer.writerow(
            {
                "store_id": _cell(row.id),
                "code": _cell(row.code),
                "name": _cell(row.name),
                "drawer_mode": _cell(cfg.get("drawer_mode")),
                "drawer_host": _cell(cfg.get("drawer_host")),
                "drawer_port": _cell(cfg.get("drawer_port")),
                "drawer_open_on_cash": _cell(bool(cfg.get("drawer_open_on_cash"))),
                "is_active": _cell(bool(getattr(row, "is_active", True))),
            }
        )
    return buf.getvalue()


async def export_store_inventory_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    include_zero: bool = False,
    company_id: str | None = None,
) -> str:
    """Stage 155 I1 — store warehouse inventory / reorder CSV."""
    rows = await stores_svc.store_inventory(
        db, tenant_id, store_id, include_zero=include_zero, company_id=company_id
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STORE_INVENTORY_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "store_id": _cell(store_id),
                "warehouse_id": _cell(row.get("warehouse_id")),
                "product_id": _cell(row.get("product_id")),
                "sku": _cell(row.get("sku")),
                "name": _cell(row.get("name")),
                "quantity": _cell(row.get("quantity")),
                "reorder_level": _cell(row.get("reorder_level")),
                "reorder_qty": _cell(row.get("reorder_qty")),
                "below_reorder": _cell(bool(row.get("below_reorder"))),
                "suggested_order_qty": _cell(row.get("suggested_order_qty")),
                "consolidated_stock": _cell(row.get("consolidated_stock")),
            }
        )
    return buf.getvalue()


async def export_store_sales_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    recent_limit: int = 50,
    company_id: str | None = None,
) -> str:
    """Stage 155 S1 — store sales summary + recent invoice/POS lines CSV."""
    payload = await stores_svc.store_sales(
        db,
        tenant_id,
        store_id,
        from_date=from_date,
        to_date=to_date,
        recent_limit=recent_limit,
        company_id=company_id,
    )
    store = payload.get("store") or {}
    summary = payload.get("summary") or {}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STORE_SALES_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "store_id": _cell(store.get("id") or store_id),
            "store_code": _cell(store.get("code")),
            "store_name": _cell(store.get("name")),
            "row_type": "summary",
            "source": "",
            "record_id": "",
            "number": "",
            "total": _cell(summary.get("revenue")),
            "tax": _cell(summary.get("tax")),
            "status": "",
            "occurred_at": "",
            "invoice_count": _cell(summary.get("invoice_count")),
            "pos_count": _cell(summary.get("pos_count")),
            "sale_count": _cell(summary.get("sale_count")),
            "revenue": _cell(summary.get("revenue")),
            "avg_ticket": _cell(summary.get("avg_ticket")),
            "from_date": _cell(payload.get("from_date")),
            "to_date": _cell(payload.get("to_date")),
        }
    )
    for row in payload.get("recent") or []:
        writer.writerow(
            {
                "store_id": _cell(store.get("id") or store_id),
                "store_code": _cell(store.get("code")),
                "store_name": _cell(store.get("name")),
                "row_type": "sale",
                "source": _cell(row.get("source")),
                "record_id": _cell(row.get("id")),
                "number": _cell(row.get("number")),
                "total": _cell(row.get("total")),
                "tax": _cell(row.get("tax")),
                "status": _cell(row.get("status")),
                "occurred_at": _cell(row.get("occurred_at")),
                "invoice_count": "",
                "pos_count": "",
                "sale_count": "",
                "revenue": "",
                "avg_ticket": "",
                "from_date": "",
                "to_date": "",
            }
        )
    return buf.getvalue()
