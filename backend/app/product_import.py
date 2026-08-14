"""CSV bulk import for products (template + dry-run/commit)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import barcodes as barcode_svc
from app import catalog_meta as catalog_meta_svc
from app import models as m
from app.inventory import apply_stock_change

TEMPLATE_COLUMNS = [
    "name",
    "sku",
    "barcode",
    "category_code",
    "brand_code",
    "unit_code",
    "cost_price",
    "selling_price",
    "reorder_level",
    "stock_qty",
    "tracks_batches",
]


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "name": "Sample Widget",
            "sku": "SKU-001",
            "barcode": "",
            "category_code": "GEN",
            "brand_code": "",
            "unit_code": "PCS",
            "cost_price": "1.00",
            "selling_price": "2.50",
            "reorder_level": "5",
            "stock_qty": "0",
            "tracks_batches": "false",
        }
    )
    return buf.getvalue()


async def export_products_csv(
    db: AsyncSession, *, tenant_id: str, company_id: str | None = None
) -> str:
    """Stage 118 E1 — export tenant products using the same columns as the import template."""
    await catalog_meta_svc.ensure_default_catalog(db, tenant_id, company_id=company_id)
    cat_q = select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id)
    brand_q = select(m.Brand).where(m.Brand.tenant_id == tenant_id)
    unit_q = select(m.UnitOfMeasure).where(m.UnitOfMeasure.tenant_id == tenant_id)
    prod_q = select(m.Product).where(m.Product.tenant_id == tenant_id)
    if company_id:
        cat_q = cat_q.where(m.ProductCategory.company_id == company_id)
        brand_q = brand_q.where(m.Brand.company_id == company_id)
        unit_q = unit_q.where(m.UnitOfMeasure.company_id == company_id)
        prod_q = prod_q.where(m.Product.company_id == company_id)
    cats = {
        c.id: c.code
        for c in (await db.execute(cat_q)).scalars().all()
    }
    brands = {
        b.id: b.code
        for b in (await db.execute(brand_q)).scalars().all()
    }
    units = {
        u.id: u.code
        for u in (await db.execute(unit_q)).scalars().all()
    }
    products = (
        await db.execute(prod_q.order_by(m.Product.sku))
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    for p in products:
        writer.writerow(
            {
                "name": p.name or "",
                "sku": p.sku or "",
                "barcode": p.barcode or "",
                "category_code": cats.get(p.category_id) or "",
                "brand_code": brands.get(p.brand_id) or "",
                "unit_code": units.get(p.unit_id) or "",
                "cost_price": f"{float(p.cost_price or 0):.2f}",
                "selling_price": f"{float(p.selling_price or 0):.2f}",
                "reorder_level": f"{float(p.reorder_level or 0):.2f}",
                "stock_qty": f"{float(p.stock_qty or 0):.2f}",
                "tracks_batches": "true" if p.tracks_batches else "false",
            }
        )
    return buf.getvalue()


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def _parse_bool(value: str | None) -> bool:
    text = (value or "").strip().lower()
    if text in {"", "0", "false", "no", "n"}:
        return False
    if text in {"1", "true", "yes", "y"}:
        return True
    raise ValueError("must be true/false")


def _parse_float(value: str | None, *, default: float = 0.0) -> float:
    text = (value or "").strip()
    if not text:
        return default
    return float(text.replace(",", ""))


def parse_product_csv(content: str) -> list[dict[str, str]]:
    sample = content.lstrip("\ufeff")
    if not sample.strip():
        raise HTTPException(status_code=400, detail="Empty CSV")
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(sample), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    header_map: dict[str, str] = {}
    for raw in reader.fieldnames:
        key = _norm_header(raw)
        if key in TEMPLATE_COLUMNS and key not in header_map:
            header_map[key] = raw
    if "name" not in header_map or "sku" not in header_map:
        raise HTTPException(status_code=400, detail="CSV must include name and sku columns")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if not any((v or "").strip() for v in raw_row.values()):
            continue
        rows.append({col: (raw_row.get(header_map[col]) or "").strip() if col in header_map else "" for col in TEMPLATE_COLUMNS})
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    if len(rows) > 2000:
        raise HTTPException(status_code=400, detail="CSV exceeds maximum of 2000 rows")
    return rows


async def _lookup_code_maps(db: AsyncSession, tenant_id: str) -> tuple[dict[str, m.ProductCategory], dict[str, m.Brand], dict[str, m.UnitOfMeasure]]:
    await catalog_meta_svc.ensure_default_catalog(db, tenant_id)
    cats = {
        c.code.upper(): c
        for c in (
            await db.execute(select(m.ProductCategory).where(m.ProductCategory.tenant_id == tenant_id))
        ).scalars().all()
    }
    brands = {
        b.code.upper(): b
        for b in (await db.execute(select(m.Brand).where(m.Brand.tenant_id == tenant_id))).scalars().all()
    }
    units = {
        u.code.upper(): u
        for u in (
            await db.execute(select(m.UnitOfMeasure).where(m.UnitOfMeasure.tenant_id == tenant_id))
        ).scalars().all()
    }
    return cats, brands, units


async def import_products_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    content: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    rows = parse_product_csv(content)
    cats, brands, units = await _lookup_code_maps(db, tenant_id)

    existing_skus = set(
        (
            await db.execute(select(m.Product.sku).where(m.Product.tenant_id == tenant_id))
        ).scalars().all()
    )
    existing_barcodes = {
        b
        for b in (
            await db.execute(
                select(m.Product.barcode).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.barcode.is_not(None),
                )
            )
        ).scalars().all()
        if b
    }
    existing_barcodes.update(
        {
            b
            for b in (
                await db.execute(
                    select(m.ProductVariant.barcode).where(
                        m.ProductVariant.tenant_id == tenant_id,
                        m.ProductVariant.barcode.is_not(None),
                    )
                )
            ).scalars().all()
            if b
        }
    )

    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()
    errors: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):  # header is row 1
        row_errors: list[str] = []
        name = row["name"].strip()
        sku = row["sku"].strip()
        if not name:
            row_errors.append("name is required")
        if not sku:
            row_errors.append("sku is required")
        elif sku in existing_skus or sku in seen_skus:
            row_errors.append("sku already exists")
        barcode = None
        if row["barcode"]:
            try:
                barcode = barcode_svc.validate_barcode(row["barcode"])
            except HTTPException as exc:
                row_errors.append(str(exc.detail))
            else:
                if barcode in existing_barcodes or barcode in seen_barcodes:
                    row_errors.append("barcode already in use")

        category_id = None
        category_label = "General"
        if row["category_code"]:
            cat = cats.get(row["category_code"].upper())
            if not cat or not cat.is_active:
                row_errors.append(f"unknown category_code {row['category_code']}")
            else:
                category_id = cat.id
                category_label = cat.name

        brand_id = None
        if row["brand_code"]:
            brand = brands.get(row["brand_code"].upper())
            if not brand or not brand.is_active:
                row_errors.append(f"unknown brand_code {row['brand_code']}")
            else:
                brand_id = brand.id

        unit_id = None
        if row["unit_code"]:
            unit = units.get(row["unit_code"].upper())
            if not unit or not unit.is_active:
                row_errors.append(f"unknown unit_code {row['unit_code']}")
            else:
                unit_id = unit.id

        try:
            cost_price = _parse_float(row["cost_price"])
            selling_price = _parse_float(row["selling_price"])
            reorder_level = _parse_float(row["reorder_level"])
            stock_qty = _parse_float(row["stock_qty"])
            tracks_batches = _parse_bool(row["tracks_batches"])
        except ValueError as exc:
            row_errors.append(f"numeric/boolean parse error: {exc}")
            cost_price = selling_price = reorder_level = stock_qty = 0.0
            tracks_batches = False

        if row_errors:
            errors.append({"row": idx, "sku": sku or None, "errors": row_errors})
            continue

        seen_skus.add(sku)
        if barcode:
            seen_barcodes.add(barcode)
        valid_rows.append(
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
                "reorder_level": reorder_level,
                "stock_qty": stock_qty,
                "tracks_batches": tracks_batches,
            }
        )

    created: list[dict[str, Any]] = []
    if not dry_run and valid_rows:
        for data in valid_rows:
            opening = float(data.pop("stock_qty") or 0)
            product = m.Product(tenant_id=tenant_id, stock_qty=0, is_active=True, **data)
            db.add(product)
            await db.flush()
            if opening > 0:
                await apply_stock_change(
                    db,
                    tenant_id=tenant_id,
                    product_id=product.id,
                    quantity_delta=opening,
                    movement_type="opening_stock",
                    user_id=user_id,
                    reference_type="product_import",
                    reference_id=product.id,
                    notes="Opening stock from CSV import",
                )
            created.append(catalog_meta_svc.serialize_product(product) | {"imported_stock_qty": opening})
        await db.flush()

    return {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "error_rows": len(errors),
        "errors": errors[:100],
        "created": created if not dry_run else [],
        "preview": [
            {"sku": r["sku"], "name": r["name"], "barcode": r["barcode"], "stock_qty": r["stock_qty"]}
            for r in valid_rows[:20]
        ]
        if dry_run
        else [],
    }
