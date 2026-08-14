"""CSV export for stock movements, low-stock alerts, expiring batches (Stage 137),
product batches (Stage 154), and product warehouse-stock (Stage 155 W1)."""

from __future__ import annotations

import csv
import io

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalog as catalog_svc
from app import models as m
from app import reports as reports_svc
from app.inventory import (
    compute_stock_status,
    effective_warehouse_thresholds,
    list_movements_serialized,
)
from app.session_passkey_doc_export import _cell

MOVEMENT_EXPORT_COLUMNS = [
    "id",
    "product_id",
    "product_sku",
    "product_name",
    "variant_id",
    "batch_id",
    "warehouse_id",
    "warehouse_code",
    "movement_type",
    "quantity",
    "quantity_before",
    "quantity_after",
    "reference_type",
    "reference_id",
    "reason",
    "notes",
    "created_by",
    "created_by_email",
    "created_at",
]

LOW_STOCK_EXPORT_COLUMNS = [
    "id",
    "sku",
    "name",
    "scope",
    "warehouse_id",
    "warehouse_code",
    "stock_qty",
    "minimum_stock",
    "reorder_level",
    "stock_status",
    "cost_price",
    "suggested_order_qty",
]

EXPIRING_BATCH_EXPORT_COLUMNS = [
    "id",
    "product_id",
    "variant_id",
    "warehouse_id",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "quantity",
    "created_at",
    "updated_at",
]

PRODUCT_BATCH_EXPORT_COLUMNS = [
    "id",
    "product_id",
    "variant_id",
    "warehouse_id",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "quantity",
    "created_at",
    "updated_at",
]

PRODUCT_WAREHOUSE_STOCK_EXPORT_COLUMNS = [
    "product_id",
    "product_sku",
    "product_name",
    "consolidated_qty",
    "consolidated_minimum_stock",
    "consolidated_reorder_level",
    "consolidated_stock_status",
    "consolidated_reserved_qty",
    "consolidated_available_qty",
    "warehouse_id",
    "warehouse_code",
    "warehouse_name",
    "quantity",
    "reserved_qty",
    "available_qty",
    "minimum_stock",
    "reorder_level",
    "reorder_qty",
    "stock_status",
]

STOCK_STATUSES = {"red", "yellow"}
MOVEMENT_TYPES = {
    "stock_in",
    "stock_out",
    "opening_stock",
    "adjustment",
    "transfer_out",
    "transfer_in",
}


def _normalize_stock_status(stock_status: str | None) -> str | None:
    if not stock_status:
        return None
    key = stock_status.strip().lower()
    if key not in STOCK_STATUSES:
        raise HTTPException(status_code=400, detail="stock_status must be red or yellow")
    return key


async def list_low_stock_alerts(
    db: AsyncSession,
    *,
    tenant_id: str,
    stock_status: str | None = None,
    company_id: str | None = None,
) -> list[dict]:
    status_filter = _normalize_stock_status(stock_status)
    prod_stmt = (
        select(m.Product)
        .where(
            m.Product.tenant_id == tenant_id,
            m.Product.is_active == True,  # noqa: E712
        )
        .order_by(m.Product.stock_qty.asc())
    )
    if company_id:
        prod_stmt = prod_stmt.where(m.Product.company_id == company_id)
    products = (await db.execute(prod_stmt)).scalars().all()
    out: list[dict] = []
    for p in products:
        qty = float(p.stock_qty or 0)
        minimum = float(getattr(p, "minimum_stock", 0) or 0)
        reorder = float(p.reorder_level or 0)
        status = compute_stock_status(qty, minimum, reorder)
        if status == "green":
            continue
        if status_filter and status != status_filter:
            continue
        out.append(
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": qty,
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": status,
                "cost_price": float(p.cost_price or 0),
                "scope": "product",
                "warehouse_id": None,
                "warehouse_code": None,
                "suggested_order_qty": max(
                    1.0,
                    round(reorder - qty, 3) if reorder > qty else max(reorder, 1.0),
                ),
            }
        )

    wh_stmt = (
        select(m.WarehouseStock, m.Product, m.Warehouse)
        .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
        .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
        .where(
            m.WarehouseStock.tenant_id == tenant_id,
            m.Product.is_active == True,  # noqa: E712
        )
        .order_by(m.WarehouseStock.quantity.asc())
    )
    if company_id:
        wh_stmt = wh_stmt.where(
            m.Product.company_id == company_id,
            m.Warehouse.company_id == company_id,
        )
    wh_rows = (await db.execute(wh_stmt)).all()
    for stock, product, wh in wh_rows:
        qty = float(stock.quantity or 0)
        minimum, reorder = effective_warehouse_thresholds(stock, product)
        status = compute_stock_status(qty, minimum, reorder)
        if status == "green":
            continue
        w_min = float(getattr(stock, "minimum_stock", 0) or 0)
        w_ro = float(stock.reorder_level or 0)
        if w_min <= 0 and w_ro <= 0:
            continue
        if status_filter and status != status_filter:
            continue
        out.append(
            {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_qty": qty,
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": status,
                "cost_price": float(product.cost_price or 0),
                "scope": "warehouse",
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "suggested_order_qty": max(
                    1.0,
                    float(stock.reorder_qty or 0)
                    or (round(reorder - qty, 3) if reorder > qty else max(reorder, 1.0)),
                ),
            }
        )
    return out


async def export_movements_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    movement_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    company_id: str | None = None,
) -> str:
    if movement_type:
        key = movement_type.strip().lower()
        if key not in MOVEMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    "movement_type must be stock_in, stock_out, opening_stock, "
                    "adjustment, transfer_out, or transfer_in"
                ),
            )
        movement_type = key
    rows = await list_movements_serialized(
        db,
        tenant_id=tenant_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        from_dt=reports_svc.parse_date(from_date),
        to_dt=reports_svc.parse_date(to_date, end_of_day=True),
        limit=500,
        company_id=company_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=MOVEMENT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in MOVEMENT_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_low_stock_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    stock_status: str | None = None,
    company_id: str | None = None,
) -> str:
    rows = await list_low_stock_alerts(
        db, tenant_id=tenant_id, stock_status=stock_status, company_id=company_id
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LOW_STOCK_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in LOW_STOCK_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_expiring_batches_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    days: int = 30,
    company_id: str | None = None,
) -> str:
    days_n = max(0, min(int(days), 3650))
    rows = await catalog_svc.list_expiring_batches(
        db, tenant_id, within_days=days_n, company_id=company_id
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPIRING_BATCH_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = catalog_svc.serialize_batch(row)
        writer.writerow({k: _cell(data.get(k)) for k in EXPIRING_BATCH_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_product_batches_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
) -> str:
    """Stage 154 K1 — per-product batches CSV (distinct from Stage 137 expiring window)."""
    await catalog_svc.get_product(db, tenant_id, product_id)
    rows = await catalog_svc.list_batches(db, tenant_id, product_id=product_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PRODUCT_BATCH_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = catalog_svc.serialize_batch(row)
        writer.writerow({k: _cell(data.get(k)) for k in PRODUCT_BATCH_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_product_warehouse_stock_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
) -> str:
    """Stage 155 W1 — per-product warehouse placement CSV (distinct from Stage 137 movements)."""
    product = await catalog_svc.get_product(db, tenant_id, product_id)
    rows = (
        await db.execute(
            select(m.WarehouseStock, m.Warehouse)
            .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
            .where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.product_id == product_id,
            )
            .order_by(m.Warehouse.code)
        )
    ).all()
    p_min = float(getattr(product, "minimum_stock", 0) or 0)
    p_ro = float(product.reorder_level or 0)
    p_qty = float(product.stock_qty or 0)
    p_reserved = float(getattr(product, "reserved_qty", 0) or 0)
    consolidated_status = compute_stock_status(p_qty, p_min, p_ro)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PRODUCT_WAREHOUSE_STOCK_EXPORT_COLUMNS)
    writer.writeheader()
    if not rows:
        writer.writerow(
            {
                "product_id": _cell(product.id),
                "product_sku": _cell(product.sku),
                "product_name": _cell(product.name),
                "consolidated_qty": _cell(p_qty),
                "consolidated_minimum_stock": _cell(p_min),
                "consolidated_reorder_level": _cell(p_ro),
                "consolidated_stock_status": _cell(consolidated_status),
                "consolidated_reserved_qty": _cell(p_reserved),
                "consolidated_available_qty": _cell(max(p_qty - p_reserved, 0.0)),
                "warehouse_id": "",
                "warehouse_code": "",
                "warehouse_name": "",
                "quantity": "",
                "reserved_qty": "",
                "available_qty": "",
                "minimum_stock": "",
                "reorder_level": "",
                "reorder_qty": "",
                "stock_status": "",
            }
        )
        return buf.getvalue()
    for stock, wh in rows:
        qty = float(stock.quantity or 0)
        reserved = float(getattr(stock, "reserved_qty", 0) or 0)
        minimum, reorder = effective_warehouse_thresholds(stock, product)
        writer.writerow(
            {
                "product_id": _cell(product.id),
                "product_sku": _cell(product.sku),
                "product_name": _cell(product.name),
                "consolidated_qty": _cell(p_qty),
                "consolidated_minimum_stock": _cell(p_min),
                "consolidated_reorder_level": _cell(p_ro),
                "consolidated_stock_status": _cell(consolidated_status),
                "consolidated_reserved_qty": _cell(p_reserved),
                "consolidated_available_qty": _cell(max(p_qty - p_reserved, 0.0)),
                "warehouse_id": _cell(wh.id),
                "warehouse_code": _cell(wh.code),
                "warehouse_name": _cell(wh.name),
                "quantity": _cell(qty),
                "reserved_qty": _cell(reserved),
                "available_qty": _cell(max(qty - reserved, 0.0)),
                "minimum_stock": _cell(minimum),
                "reorder_level": _cell(reorder),
                "reorder_qty": _cell(float(stock.reorder_qty or 0)),
                "stock_status": _cell(compute_stock_status(qty, minimum, reorder)),
            }
        )
    return buf.getvalue()
