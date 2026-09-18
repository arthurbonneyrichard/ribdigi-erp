"""CSV bulk import for product variants (template + dry-run/commit).

Creates or updates catalog fields only. stock_qty from export files is ignored —
stock mutations stay on the inventory engine, not this import.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import barcodes as barcode_svc
from app import catalog as catalog_svc
from app import models as m

TEMPLATE_COLUMNS = [
    "product_sku",
    "product_id",
    "name",
    "sku",
    "barcode",
    "size",
    "color",
    "flavor",
    "cost_price",
    "selling_price",
    "is_active",
]


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "product_sku": "A-1",
            "product_id": "",
            "name": "Large",
            "sku": "A-1-L",
            "barcode": "",
            "size": "L",
            "color": "Blue",
            "flavor": "",
            "cost_price": "1.00",
            "selling_price": "2.50",
            "is_active": "true",
        }
    )
    return buf.getvalue()


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def _parse_optional_bool(value: str | None) -> bool | None:
    text = (value or "").strip().lower()
    if not text:
        return None
    if text in {"0", "false", "no", "n"}:
        return False
    if text in {"1", "true", "yes", "y"}:
        return True
    raise ValueError("is_active must be true/false")


def _parse_optional_float(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    return float(text.replace(",", ""))


def parse_variant_csv(content: str) -> list[dict[str, str]]:
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
    if "product_sku" not in header_map and "product_id" not in header_map:
        raise HTTPException(
            status_code=400, detail="CSV must include product_sku or product_id"
        )

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if not any((v or "").strip() for v in raw_row.values()):
            continue
        rows.append(
            {
                col: (raw_row.get(header_map[col]) or "").strip() if col in header_map else ""
                for col in TEMPLATE_COLUMNS
            }
        )
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    if len(rows) > 2000:
        raise HTTPException(status_code=400, detail="CSV exceeds maximum of 2000 rows")
    return rows


async def _load_parent_maps(
    db: AsyncSession, *, tenant_id: str, company_id: str | None
) -> tuple[dict[str, m.Product], dict[str, m.Product]]:
    stmt = select(m.Product).where(m.Product.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.Product.company_id == company_id)
    products = list((await db.execute(stmt)).scalars().all())
    by_sku = {p.sku: p for p in products if p.sku}
    by_id = {p.id: p for p in products}
    return by_sku, by_id


async def import_variants_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    content: str,
    dry_run: bool = True,
    company_id: str | None = None,
) -> dict[str, Any]:
    rows = parse_variant_csv(content)
    products_by_sku, products_by_id = await _load_parent_maps(
        db, tenant_id=tenant_id, company_id=company_id
    )

    sku_q = select(m.Product.sku).where(m.Product.tenant_id == tenant_id)
    variant_q = select(m.ProductVariant).where(m.ProductVariant.tenant_id == tenant_id)
    barcode_q = select(m.Product.barcode).where(
        m.Product.tenant_id == tenant_id,
        m.Product.barcode.is_not(None),
    )
    variant_barcode_q = select(m.ProductVariant.barcode).where(
        m.ProductVariant.tenant_id == tenant_id,
        m.ProductVariant.barcode.is_not(None),
    )
    if company_id:
        sku_q = sku_q.where(m.Product.company_id == company_id)
        variant_q = variant_q.where(m.ProductVariant.company_id == company_id)
        barcode_q = barcode_q.where(m.Product.company_id == company_id)
        variant_barcode_q = variant_barcode_q.where(m.ProductVariant.company_id == company_id)

    product_skus = {s for s in (await db.execute(sku_q)).scalars().all() if s}
    existing_variants = list((await db.execute(variant_q)).scalars().all())
    variants_by_sku = {v.sku: v for v in existing_variants if v.sku}
    existing_barcodes = {b for b in (await db.execute(barcode_q)).scalars().all() if b}
    existing_barcodes.update(
        {b for b in (await db.execute(variant_barcode_q)).scalars().all() if b}
    )

    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()
    errors: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        row_errors: list[str] = []
        name = row["name"].strip()
        sku = row["sku"].strip()
        product_sku = row["product_sku"].strip()
        product_id = row["product_id"].strip()

        if not name:
            row_errors.append("name is required")
        if not sku:
            row_errors.append("sku is required")
        elif sku in seen_skus:
            row_errors.append("duplicate sku in file")

        parent: m.Product | None = None
        if product_id:
            parent = products_by_id.get(product_id)
            if parent is None:
                row_errors.append(f"unknown product_id {product_id}")
            elif product_sku and parent.sku != product_sku:
                row_errors.append("product_id does not match product_sku")
        elif product_sku:
            parent = products_by_sku.get(product_sku)
            if parent is None:
                row_errors.append(f"unknown product_sku {product_sku}")
        else:
            row_errors.append("product_sku or product_id is required")

        existing = variants_by_sku.get(sku)
        action = "update" if existing is not None else "create"
        if existing is not None and parent is not None and existing.product_id != parent.id:
            row_errors.append("sku already used by another product's variant")
        if existing is None and sku in product_skus:
            row_errors.append("sku already used by a product")

        barcode = None
        if row["barcode"]:
            try:
                barcode = barcode_svc.validate_barcode(row["barcode"])
            except HTTPException as exc:
                row_errors.append(str(exc.detail))
            else:
                held_by_self = existing is not None and existing.barcode == barcode
                if (
                    barcode
                    and not held_by_self
                    and (barcode in existing_barcodes or barcode in seen_barcodes)
                ):
                    row_errors.append("barcode already in use")

        try:
            cost_price = _parse_optional_float(row["cost_price"])
            selling_price = _parse_optional_float(row["selling_price"])
            is_active = _parse_optional_bool(row["is_active"])
        except ValueError as exc:
            row_errors.append(f"numeric/boolean parse error: {exc}")
            cost_price = selling_price = None
            is_active = None

        if row_errors:
            errors.append({"row": idx, "sku": sku or None, "errors": row_errors})
            continue

        assert parent is not None
        seen_skus.add(sku)
        if barcode:
            seen_barcodes.add(barcode)
        valid_rows.append(
            {
                "action": action,
                "product_id": parent.id,
                "product_sku": parent.sku,
                "existing_id": existing.id if existing is not None else None,
                "name": name,
                "sku": sku,
                "barcode": barcode,
                "size": row["size"].strip() or None,
                "color": row["color"].strip() or None,
                "flavor": row["flavor"].strip() or None,
                "cost_price": cost_price,
                "selling_price": selling_price,
                "is_active": is_active,
            }
        )

    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    if not dry_run and valid_rows:
        for data in valid_rows:
            action = data["action"]
            if action == "create":
                variant = await catalog_svc.create_variant(
                    db,
                    tenant_id=tenant_id,
                    product_id=data["product_id"],
                    name=data["name"],
                    sku=data["sku"],
                    barcode=data["barcode"],
                    size=data["size"],
                    color=data["color"],
                    flavor=data["flavor"],
                    cost_price=data["cost_price"],
                    selling_price=data["selling_price"],
                )
                if data["is_active"] is False:
                    variant = await catalog_svc.update_variant(
                        db,
                        tenant_id=tenant_id,
                        product_id=data["product_id"],
                        variant_id=variant.id,
                        is_active=False,
                    )
                created.append(catalog_svc.serialize_variant(variant))
            else:
                variant = await catalog_svc.update_variant(
                    db,
                    tenant_id=tenant_id,
                    product_id=data["product_id"],
                    variant_id=data["existing_id"],
                    name=data["name"],
                    barcode=data["barcode"],
                    size=data["size"],
                    color=data["color"],
                    flavor=data["flavor"],
                    cost_price=data["cost_price"],
                    selling_price=data["selling_price"],
                    is_active=data["is_active"],
                )
                updated.append(catalog_svc.serialize_variant(variant))
        await db.flush()

    return {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "error_rows": len(errors),
        "create_count": sum(1 for r in valid_rows if r["action"] == "create"),
        "update_count": sum(1 for r in valid_rows if r["action"] == "update"),
        "errors": errors[:100],
        "created": created if not dry_run else [],
        "updated": updated if not dry_run else [],
        "preview": [
            {
                "action": r["action"],
                "product_sku": r["product_sku"],
                "sku": r["sku"],
                "name": r["name"],
                "barcode": r["barcode"],
            }
            for r in valid_rows[:20]
        ]
        if dry_run
        else [],
    }
