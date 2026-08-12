"""Product CSV bulk import (validate + all-or-nothing commit)."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import barcodes as barcodes_svc
from app import catalog_meta as catalog_meta_svc
from app import models as m
from app.inventory import apply_stock_change

TEMPLATE_HEADERS = (
    "name",
    "sku",
    "barcode",
    "category",
    "brand",
    "unit",
    "cost_price",
    "selling_price",
    "stock_qty",
    "reorder_level",
    "tax_exempt",
    "tracks_batches",
)

SAMPLE_ROW = {
    "name": "Bottled Water 500ml",
    "sku": "WATER-500",
    "barcode": "WATER-500",
    "category": "Beverages",
    "brand": "",
    "unit": "PCS",
    "cost_price": "2.00",
    "selling_price": "5.00",
    "stock_qty": "100",
    "reorder_level": "20",
    "tax_exempt": "false",
    "tracks_batches": "false",
}


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(TEMPLATE_HEADERS))
    writer.writeheader()
    writer.writerow(SAMPLE_ROW)
    return buf.getvalue()


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "t"}


def _parse_float(value: str | None, *, field: str, default: float = 0.0) -> float:
    text = (value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be a number") from exc


def _norm_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def parse_csv_rows(content: str) -> list[dict[str, str]]:
    text = (content or "").lstrip("\ufeff")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty CSV")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is missing a header row")
    mapping = {_norm_header(h): h for h in reader.fieldnames if h}
    if "name" not in mapping or "sku" not in mapping:
        raise HTTPException(
            status_code=400,
            detail="CSV must include name and sku columns",
        )
    rows: list[dict[str, str]] = []
    for raw in reader:
        if not any((v or "").strip() for v in raw.values()):
            continue
        rows.append(
            {
                key: (raw.get(mapping[key]) or "").strip() if key in mapping else ""
                for key in TEMPLATE_HEADERS
            }
        )
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    if len(rows) > 2000:
        raise HTTPException(status_code=400, detail="CSV exceeds 2000 row limit")
    return rows


async def _lookup_category(
    db: AsyncSession, tenant_id: str, value: str
) -> tuple[str | None, str]:
    text = value.strip()
    if not text:
        return None, "General"
    row = (
        await db.execute(
            select(m.ProductCategory).where(
                m.ProductCategory.tenant_id == tenant_id,
                m.ProductCategory.is_active == True,  # noqa: E712
                (func.lower(m.ProductCategory.name) == text.lower())
                | (func.lower(m.ProductCategory.code) == text.lower()),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise ValueError(f"Unknown category '{text}'")
    return row.id, row.name


async def _lookup_brand(db: AsyncSession, tenant_id: str, value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    row = (
        await db.execute(
            select(m.Brand).where(
                m.Brand.tenant_id == tenant_id,
                m.Brand.is_active == True,  # noqa: E712
                (func.lower(m.Brand.name) == text.lower())
                | (func.lower(m.Brand.code) == text.lower()),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise ValueError(f"Unknown brand '{text}'")
    return row.id


async def _lookup_unit(db: AsyncSession, tenant_id: str, value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    row = (
        await db.execute(
            select(m.UnitOfMeasure).where(
                m.UnitOfMeasure.tenant_id == tenant_id,
                m.UnitOfMeasure.is_active == True,  # noqa: E712
                (func.lower(m.UnitOfMeasure.code) == text.lower())
                | (func.lower(m.UnitOfMeasure.name) == text.lower()),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise ValueError(f"Unknown unit '{text}'")
    return row.id


async def _sku_exists(db: AsyncSession, tenant_id: str, sku: str) -> bool:
    hit = (
        await db.execute(
            select(m.Product.id).where(
                m.Product.tenant_id == tenant_id,
                func.lower(m.Product.sku) == sku.lower(),
            )
        )
    ).scalar_one_or_none()
    return hit is not None


async def _barcode_exists(db: AsyncSession, tenant_id: str, barcode: str) -> bool:
    hit = (
        await db.execute(
            select(m.Product.id).where(
                m.Product.tenant_id == tenant_id,
                m.Product.barcode == barcode,
            )
        )
    ).scalar_one_or_none()
    return hit is not None


async def validate_import_rows(
    db: AsyncSession,
    *,
    tenant_id: str,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    report_rows: list[dict[str, Any]] = []
    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()
    prepared: list[dict[str, Any]] = []

    for idx, raw in enumerate(rows, start=2):  # header is line 1
        errors: list[str] = []
        name = (raw.get("name") or "").strip()
        sku = (raw.get("sku") or "").strip()
        if not name:
            errors.append("name is required")
        if not sku:
            errors.append("sku is required")
        sku_key = sku.lower()
        if sku and sku_key in seen_skus:
            errors.append("duplicate sku in file")
        if sku:
            seen_skus.add(sku_key)

        barcode = None
        try:
            barcode = barcodes_svc.normalize_barcode(raw.get("barcode") or None)
        except HTTPException as exc:
            errors.append(str(exc.detail))
        if barcode:
            if barcode in seen_barcodes:
                errors.append("duplicate barcode in file")
            seen_barcodes.add(barcode)

        cost_price = selling_price = stock_qty = reorder_level = 0.0
        try:
            cost_price = _parse_float(raw.get("cost_price"), field="cost_price")
            selling_price = _parse_float(raw.get("selling_price"), field="selling_price")
            stock_qty = _parse_float(raw.get("stock_qty"), field="stock_qty")
            reorder_level = _parse_float(raw.get("reorder_level"), field="reorder_level")
            if cost_price < 0 or selling_price < 0 or stock_qty < 0 or reorder_level < 0:
                errors.append("prices and quantities must be >= 0")
        except ValueError as exc:
            errors.append(str(exc))

        category_id = None
        category_label = "General"
        brand_id = None
        unit_id = None
        try:
            category_id, category_label = await _lookup_category(
                db, tenant_id, raw.get("category") or ""
            )
            brand_id = await _lookup_brand(db, tenant_id, raw.get("brand") or "")
            unit_id = await _lookup_unit(db, tenant_id, raw.get("unit") or "")
        except ValueError as exc:
            errors.append(str(exc))

        if sku and await _sku_exists(db, tenant_id, sku):
            errors.append("sku already exists")
        if barcode and await _barcode_exists(db, tenant_id, barcode):
            errors.append("barcode already exists")

        ok = not errors
        report_rows.append(
            {
                "line": idx,
                "sku": sku,
                "name": name,
                "ok": ok,
                "errors": errors,
            }
        )
        if ok:
            prepared.append(
                {
                    "name": name,
                    "sku": sku,
                    "barcode": barcode,
                    "category": category_label,
                    "category_id": category_id,
                    "brand_id": brand_id,
                    "unit_id": unit_id,
                    "cost_price": cost_price,
                    "selling_price": selling_price,
                    "stock_qty": stock_qty,
                    "reorder_level": reorder_level,
                    "tax_exempt": _truthy(raw.get("tax_exempt")),
                    "tracks_batches": _truthy(raw.get("tracks_batches")),
                }
            )

    error_count = sum(1 for r in report_rows if not r["ok"])
    return {
        "total_rows": len(report_rows),
        "valid_rows": len(prepared),
        "error_rows": error_count,
        "can_commit": error_count == 0 and len(prepared) > 0,
        "rows": report_rows,
        "_prepared": prepared,
    }


async def commit_import(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    prepared: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for data in prepared:
        stock_qty = float(data.get("stock_qty") or 0)
        product = m.Product(
            tenant_id=tenant_id,
            name=data["name"],
            sku=data["sku"],
            barcode=data.get("barcode"),
            category=data.get("category") or "General",
            category_id=data.get("category_id"),
            brand_id=data.get("brand_id"),
            unit_id=data.get("unit_id"),
            cost_price=data.get("cost_price") or 0,
            selling_price=data.get("selling_price") or 0,
            stock_qty=0,
            reorder_level=data.get("reorder_level") or 0,
            tax_exempt=bool(data.get("tax_exempt")),
            tracks_batches=bool(data.get("tracks_batches")),
        )
        db.add(product)
        await db.flush()
        if stock_qty > 0:
            product = await apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=product.id,
                quantity_delta=stock_qty,
                movement_type="opening_stock",
                user_id=user_id,
                reference_type="product_import",
                reference_id=product.id,
                notes="Opening stock from CSV import",
            )
        else:
            await db.refresh(product)
        created.append(catalog_meta_svc.serialize_product(product))
    return created
