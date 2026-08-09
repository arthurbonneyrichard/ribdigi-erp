"""CSV bulk stock import for existing products (template + dry-run/commit)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import apply_stock_change, get_or_create_warehouse_stock

TEMPLATE_COLUMNS = [
    "sku",
    "barcode",
    "warehouse_code",
    "quantity",
    "mode",
    "reason",
]


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "sku": "A-1",
            "barcode": "",
            "warehouse_code": "",
            "quantity": "10",
            "mode": "adjust",
            "reason": "Cycle count correction",
        }
    )
    writer.writerow(
        {
            "sku": "",
            "barcode": "96385074",
            "warehouse_code": "MAIN",
            "quantity": "25",
            "mode": "set",
            "reason": "Opening stock for warehouse",
        }
    )
    return buf.getvalue()


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def _parse_float(value: str | None) -> float:
    text = (value or "").strip()
    if not text:
        raise ValueError("quantity is required")
    return float(text.replace(",", ""))


def parse_stock_csv(content: str) -> list[dict[str, str]]:
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
    if "sku" not in header_map and "barcode" not in header_map:
        raise HTTPException(status_code=400, detail="CSV must include sku and/or barcode columns")
    if "quantity" not in header_map:
        raise HTTPException(status_code=400, detail="CSV must include quantity column")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if not any((v or "").strip() for v in raw_row.values()):
            continue
        rows.append(
            {col: (raw_row.get(header_map[col]) or "").strip() if col in header_map else "" for col in TEMPLATE_COLUMNS}
        )
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    if len(rows) > 5000:
        raise HTTPException(status_code=400, detail="CSV exceeds maximum of 5000 rows")
    return rows


async def import_stock_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    content: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    rows = parse_stock_csv(content)

    products = list(
        (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id))).scalars().all()
    )
    by_sku = {str(p.sku).strip().upper(): p for p in products if p.sku}
    by_barcode = {str(p.barcode).strip(): p for p in products if p.barcode}

    warehouses = {
        w.code.upper(): w
        for w in (
            await db.execute(select(m.Warehouse).where(m.Warehouse.tenant_id == tenant_id))
        )
        .scalars()
        .all()
    }

    errors: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    # Simulate sequential effects within the file (product or product+warehouse key).
    running_qty: dict[str, float] = {}

    for idx, row in enumerate(rows, start=2):
        row_errors: list[str] = []
        sku = row["sku"].strip()
        barcode = row["barcode"].strip()
        product = None
        if sku:
            product = by_sku.get(sku.upper())
            if product is None:
                row_errors.append(f"unknown sku {sku}")
        elif barcode:
            product = by_barcode.get(barcode)
            if product is None:
                row_errors.append(f"unknown barcode {barcode}")
        else:
            row_errors.append("sku or barcode is required")

        warehouse = None
        warehouse_code = row["warehouse_code"].strip()
        if warehouse_code:
            warehouse = warehouses.get(warehouse_code.upper())
            if warehouse is None:
                row_errors.append(f"unknown warehouse_code {warehouse_code}")

        mode = (row["mode"] or "adjust").strip().lower() or "adjust"
        if mode not in {"adjust", "set"}:
            row_errors.append("mode must be adjust or set")

        try:
            quantity = _parse_float(row["quantity"])
        except ValueError as exc:
            row_errors.append(str(exc))
            quantity = 0.0

        if mode == "set" and quantity < 0:
            row_errors.append("set mode quantity cannot be negative")

        reason = row["reason"].strip() or "Stock CSV import"

        if row_errors:
            errors.append(
                {
                    "row": idx,
                    "sku": sku or None,
                    "barcode": barcode or None,
                    "errors": row_errors,
                }
            )
            continue

        assert product is not None
        scope_key = f"{product.id}:{warehouse.id if warehouse else ''}"
        if scope_key in running_qty:
            current = running_qty[scope_key]
        else:
            current = float(product.stock_qty or 0)
            if warehouse is not None:
                wh_stock = (
                    await db.execute(
                        select(m.WarehouseStock).where(
                            m.WarehouseStock.tenant_id == tenant_id,
                            m.WarehouseStock.warehouse_id == warehouse.id,
                            m.WarehouseStock.product_id == product.id,
                        )
                    )
                ).scalar_one_or_none()
                if wh_stock is not None:
                    current = float(wh_stock.quantity or 0)
                elif dry_run:
                    current = 0.0
                else:
                    wh_stock = await get_or_create_warehouse_stock(
                        db,
                        tenant_id=tenant_id,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                    )
                    current = float(wh_stock.quantity or 0)

        if mode == "set":
            delta = quantity - current
        else:
            delta = quantity

        if abs(delta) < 1e-9:
            skipped.append(
                {
                    "row": idx,
                    "sku": product.sku,
                    "barcode": product.barcode,
                    "reason": "no stock change",
                    "current_qty": current,
                }
            )
            running_qty[scope_key] = current
            continue

        after = current + delta
        if after < 0:
            errors.append(
                {
                    "row": idx,
                    "sku": product.sku,
                    "barcode": product.barcode,
                    "errors": [f"insufficient stock (available {current}, delta {delta})"],
                }
            )
            continue

        running_qty[scope_key] = after
        valid_rows.append(
            {
                "row": idx,
                "product_id": product.id,
                "sku": product.sku,
                "barcode": product.barcode,
                "warehouse_id": warehouse.id if warehouse else None,
                "warehouse_code": warehouse.code if warehouse else None,
                "mode": mode,
                "quantity": quantity,
                "current_qty": current,
                "delta": delta,
                "reason": reason,
                "movement_type": "opening_stock" if mode == "set" and current == 0 else "adjustment",
            }
        )

    applied: list[dict[str, Any]] = []
    if not dry_run and valid_rows:
        for data in valid_rows:
            product = await apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=data["product_id"],
                quantity_delta=float(data["delta"]),
                movement_type=data["movement_type"],
                user_id=user_id,
                reference_type="stock_import",
                reference_id=None,
                notes=data["reason"],
                warehouse_id=data["warehouse_id"],
            )
            applied.append(
                {
                    "row": data["row"],
                    "sku": data["sku"],
                    "barcode": data["barcode"],
                    "warehouse_code": data["warehouse_code"],
                    "mode": data["mode"],
                    "delta": data["delta"],
                    "stock_qty": float(product.stock_qty or 0),
                    "movement_type": data["movement_type"],
                }
            )
        await db.flush()

    return {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "error_rows": len(errors),
        "skipped_rows": len(skipped),
        "errors": errors[:100],
        "skipped": skipped[:50],
        "applied": applied if not dry_run else [],
        "preview": [
            {
                "sku": r["sku"],
                "barcode": r["barcode"],
                "warehouse_code": r["warehouse_code"],
                "mode": r["mode"],
                "current_qty": r["current_qty"],
                "delta": r["delta"],
                "reason": r["reason"],
            }
            for r in valid_rows[:20]
        ]
        if dry_run
        else [],
    }
