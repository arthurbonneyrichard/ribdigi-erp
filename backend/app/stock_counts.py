"""Physical stock count sessions with variance adjustments."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import allocate_unlocated_stock, apply_stock_change, get_or_create_warehouse_stock


async def get_warehouse(
    db: AsyncSession,
    tenant_id: str,
    warehouse_id: str,
    *,
    company_id: str | None = None,
) -> m.Warehouse:
    stmt = select(m.Warehouse).where(
        m.Warehouse.id == warehouse_id,
        m.Warehouse.tenant_id == tenant_id,
    )
    if company_id:
        stmt = stmt.where(m.Warehouse.company_id == company_id)
    wh = (await db.execute(stmt)).scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return wh


async def get_count(
    db: AsyncSession,
    tenant_id: str,
    count_id: str,
    *,
    company_id: str | None = None,
) -> m.StockCount:
    stmt = select(m.StockCount).where(
        m.StockCount.id == count_id,
        m.StockCount.tenant_id == tenant_id,
    )
    if company_id:
        stmt = stmt.where(m.StockCount.company_id == company_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Stock count not found")
    return row


async def list_count_items(
    db: AsyncSession, tenant_id: str, count_id: str
) -> list[m.StockCountItem]:
    return list(
        (
            await db.execute(
                select(m.StockCountItem)
                .where(
                    m.StockCountItem.tenant_id == tenant_id,
                    m.StockCountItem.stock_count_id == count_id,
                )
                .order_by(m.StockCountItem.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


def serialize_item(item: m.StockCountItem, *, product: m.Product | None = None) -> dict:
    counted = None if item.counted_qty is None else float(item.counted_qty)
    expected = float(item.expected_qty or 0)
    variance = None if counted is None else round(counted - expected, 3)
    return {
        "id": item.id,
        "company_id": getattr(item, "company_id", None),
        "product_id": item.product_id,
        "product_name": product.name if product else None,
        "product_sku": product.sku if product else None,
        "product_barcode": product.barcode if product else None,
        "expected_qty": expected,
        "counted_qty": counted,
        "variance": variance,
        "notes": item.notes,
    }


async def serialize_count(db: AsyncSession, count: m.StockCount) -> dict:
    items = await list_count_items(db, count.tenant_id, count.id)
    product_ids = [i.product_id for i in items]
    products: dict[str, m.Product] = {}
    if product_ids:
        rows = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == count.tenant_id,
                    m.Product.id.in_(product_ids),
                )
            )
        ).scalars().all()
        products = {p.id: p for p in rows}
    counted_lines = sum(1 for i in items if i.counted_qty is not None)
    warehouse = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.id == count.warehouse_id,
                m.Warehouse.tenant_id == count.tenant_id,
            )
        )
    ).scalar_one_or_none()
    return {
        "id": count.id,
        "company_id": getattr(count, "company_id", None),
        "count_number": count.count_number,
        "warehouse_id": count.warehouse_id,
        "warehouse_code": warehouse.code if warehouse else None,
        "warehouse_name": warehouse.name if warehouse else None,
        "status": count.status,
        "notes": count.notes,
        "created_by": count.created_by,
        "completed_by": count.completed_by,
        "completed_at": count.completed_at,
        "created_at": count.created_at,
        "item_count": len(items),
        "counted_item_count": counted_lines,
        "items": [serialize_item(i, product=products.get(i.product_id)) for i in items],
    }


async def list_counts(db: AsyncSession, tenant_id: str, *, limit: int = 50) -> list[m.StockCount]:
    return list(
        (
            await db.execute(
                select(m.StockCount)
                .where(m.StockCount.tenant_id == tenant_id)
                .order_by(m.StockCount.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def _resolve_product_ids(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_ids: list[str] | None,
    company_id: str | None = None,
) -> list[str]:
    from app.workspace import assert_fk_company

    if product_ids:
        ids: list[str] = []
        for pid in product_ids:
            product = (
                await db.execute(
                    select(m.Product).where(
                        m.Product.id == pid,
                        m.Product.tenant_id == tenant_id,
                        m.Product.is_active == True,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product not found: {pid}")
            assert_fk_company(product, company_id, detail=f"Product not found: {pid}")
            if pid not in ids:
                ids.append(pid)
        if not ids:
            raise HTTPException(status_code=400, detail="No valid products for stock count")
        return ids

    stock_q = select(m.WarehouseStock.product_id).where(
        m.WarehouseStock.tenant_id == tenant_id,
        m.WarehouseStock.warehouse_id == warehouse_id,
    )
    if company_id:
        stock_q = stock_q.where(m.WarehouseStock.company_id == company_id)
    stock_rows = (await db.execute(stock_q)).scalars().all()
    ids = list(dict.fromkeys(stock_rows))

    # Include products with consolidated stock not yet located at this warehouse.
    active_q = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.is_active == True,  # noqa: E712
        m.Product.stock_qty > 0,
    )
    if company_id:
        active_q = active_q.where(m.Product.company_id == company_id)
    active = (await db.execute(active_q)).scalars().all()
    for product in active:
        if product.id not in ids:
            ids.append(product.id)

    if not ids:
        # Empty warehouse: still allow a count of all active products at zero.
        empty_q = select(m.Product.id).where(
            m.Product.tenant_id == tenant_id,
            m.Product.is_active == True,  # noqa: E712
        )
        if company_id:
            empty_q = empty_q.where(m.Product.company_id == company_id)
        ids = list((await db.execute(empty_q)).scalars().all())
    if not ids:
        raise HTTPException(status_code=400, detail="No products available for stock count")
    return ids


async def create_count(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    warehouse_id: str,
    notes: str | None = None,
    product_ids: list[str] | None = None,
    company_id: str | None = None,
) -> m.StockCount:
    await get_warehouse(db, tenant_id, warehouse_id, company_id=company_id)
    ids = await _resolve_product_ids(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        product_ids=product_ids,
        company_id=company_id,
    )

    count = m.StockCount(
        tenant_id=tenant_id,
        company_id=company_id,
        warehouse_id=warehouse_id,
        count_number=f"SC-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        status="draft",
        notes=(notes or "").strip() or None,
        created_by=user_id,
    )
    db.add(count)
    await db.flush()

    for product_id in ids:
        await allocate_unlocated_stock(
            db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
        )
        stock = await get_or_create_warehouse_stock(
            db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
        )
        db.add(
            m.StockCountItem(
                tenant_id=tenant_id,
                company_id=company_id,
                stock_count_id=count.id,
                product_id=product_id,
                expected_qty=float(stock.quantity or 0),
                counted_qty=None,
            )
        )
    await db.flush()
    return count


async def update_count_items(
    db: AsyncSession,
    *,
    tenant_id: str,
    count_id: str,
    items: list[dict],
    company_id: str | None = None,
) -> m.StockCount:
    count = await get_count(db, tenant_id, count_id, company_id=company_id)
    if count.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot update count in status {count.status}")
    if not items:
        raise HTTPException(status_code=400, detail="items is required")

    existing = {i.product_id: i for i in await list_count_items(db, tenant_id, count_id)}
    for raw in items:
        product_id = str(raw.get("product_id") or "").strip()
        if not product_id or product_id not in existing:
            raise HTTPException(status_code=404, detail=f"Count line not found for product {product_id}")
        if "counted_qty" not in raw:
            raise HTTPException(status_code=400, detail="counted_qty is required for each item")
        try:
            qty = float(raw.get("counted_qty"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="counted_qty must be a number") from exc
        if qty < 0:
            raise HTTPException(status_code=400, detail="counted_qty cannot be negative")
        line = existing[product_id]
        line.counted_qty = round(qty, 3)
        if raw.get("notes") is not None:
            line.notes = str(raw.get("notes") or "").strip() or None
    await db.flush()
    return count


async def add_count_item(
    db: AsyncSession,
    *,
    tenant_id: str,
    count_id: str,
    product_id: str,
    counted_qty: float | None = None,
    notes: str | None = None,
    company_id: str | None = None,
) -> m.StockCount:
    """Add a product found during a draft count that was not on the original sheet."""
    from app.workspace import assert_fk_company

    count = await get_count(db, tenant_id, count_id, company_id=company_id)
    if count.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot add lines in status {count.status}")

    pid = (product_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="product_id is required")

    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == pid,
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product not found: {pid}")
    assert_fk_company(product, company_id, detail=f"Product not found: {pid}")

    existing = {i.product_id: i for i in await list_count_items(db, tenant_id, count_id)}
    if pid in existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COUNT_LINE_EXISTS",
                "message": "Product is already on this stock count",
                "product_id": pid,
            },
        )

    qty: float | None = None
    if counted_qty is not None:
        try:
            qty = float(counted_qty)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="counted_qty must be a number") from exc
        if qty < 0:
            raise HTTPException(status_code=400, detail="counted_qty cannot be negative")
        qty = round(qty, 3)

    await allocate_unlocated_stock(
        db, tenant_id=tenant_id, warehouse_id=count.warehouse_id, product_id=pid
    )
    stock = await get_or_create_warehouse_stock(
        db, tenant_id=tenant_id, warehouse_id=count.warehouse_id, product_id=pid
    )
    db.add(
        m.StockCountItem(
            tenant_id=tenant_id,
            company_id=company_id,
            stock_count_id=count.id,
            product_id=pid,
            expected_qty=float(stock.quantity or 0),
            counted_qty=qty,
            notes=(notes or "").strip() or None,
        )
    )
    await db.flush()
    return count


async def complete_count(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    count_id: str,
    company_id: str | None = None,
) -> m.StockCount:
    count = await get_count(db, tenant_id, count_id, company_id=company_id)
    if count.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot complete count in status {count.status}")

    items = await list_count_items(db, tenant_id, count_id)
    if not items:
        raise HTTPException(status_code=400, detail="Stock count has no lines")
    missing = [i.product_id for i in items if i.counted_qty is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"counted_qty required for all lines ({len(missing)} remaining)",
        )

    for item in items:
        expected = float(item.expected_qty or 0)
        counted = float(item.counted_qty or 0)
        variance = round(counted - expected, 3)
        if abs(variance) < 1e-9:
            continue
        await apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=item.product_id,
            quantity_delta=variance,
            movement_type="adjustment",
            user_id=user_id,
            reference_type="stock_count",
            reference_id=count.id,
            reason="other",
            notes=f"Stock count {count.count_number} variance",
            warehouse_id=count.warehouse_id,
            allow_negative=True,
        )

    count.status = "completed"
    count.completed_by = user_id
    count.completed_at = datetime.utcnow()
    await db.flush()
    return count


async def cancel_count(
    db: AsyncSession,
    *,
    tenant_id: str,
    count_id: str,
    company_id: str | None = None,
) -> m.StockCount:
    count = await get_count(db, tenant_id, count_id, company_id=company_id)
    if count.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot cancel count in status {count.status}")
    count.status = "cancelled"
    await db.flush()
    return count


VARIANCE_REPORT_FIELDS = [
    "sku",
    "name",
    "barcode",
    "expected_qty",
    "counted_qty",
    "variance_qty",
    "unit_cost",
    "variance_value",
    "notes",
]


async def build_variance_report(
    db: AsyncSession,
    *,
    tenant_id: str,
    count_id: str,
    company_id: str | None = None,
) -> dict:
    """BR-5.2 variance report for a completed stock count."""
    count = await get_count(db, tenant_id, count_id, company_id=company_id)
    if count.status != "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COUNT_NOT_COMPLETED",
                "message": "Variance report is available after the stock count is completed",
                "status": count.status,
            },
        )
    wh = await get_warehouse(db, tenant_id, count.warehouse_id)
    data = await serialize_count(db, count)
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.id.in_([i["product_id"] for i in data["items"]] or ["__none__"]),
                )
            )
        )
        .scalars()
        .all()
    }
    rows: list[dict] = []
    total_variance_qty = 0.0
    total_variance_value = 0.0
    for item in data["items"]:
        product = products.get(item["product_id"])
        expected = float(item.get("expected_qty") or 0)
        counted = float(item.get("counted_qty") or 0)
        variance = round(counted - expected, 3)
        unit_cost = float(product.cost_price or 0) if product else 0.0
        variance_value = round(variance * unit_cost, 2)
        total_variance_qty += variance
        total_variance_value += variance_value
        rows.append(
            {
                "sku": item.get("product_sku") or (product.sku if product else ""),
                "name": item.get("product_name") or (product.name if product else ""),
                "barcode": item.get("product_barcode") or (product.barcode if product else "") or "",
                "expected_qty": expected,
                "counted_qty": counted,
                "variance_qty": variance,
                "unit_cost": unit_cost,
                "variance_value": variance_value,
                "notes": item.get("notes") or "",
            }
        )
    # Non-zero variances first for readability
    rows.sort(key=lambda r: (abs(float(r["variance_qty"])) < 1e-9, r["sku"] or ""))
    return {
        "count_id": count.id,
        "count_number": count.count_number,
        "warehouse_id": wh.id,
        "warehouse_code": wh.code,
        "warehouse_name": wh.name,
        "status": count.status,
        "completed_at": count.completed_at,
        "line_count": len(rows),
        "variance_line_count": sum(1 for r in rows if abs(float(r["variance_qty"])) >= 1e-9),
        "total_variance_qty": round(total_variance_qty, 3),
        "total_variance_value": round(total_variance_value, 2),
        "rows": rows,
    }


def variance_report_csv(report: dict) -> str:
    from app.report_export import to_csv

    return to_csv(report["rows"], fieldnames=VARIANCE_REPORT_FIELDS)


def variance_report_pdf(report: dict) -> bytes:
    from app.report_export import to_pdf

    completed = report.get("completed_at")
    completed_s = completed.isoformat() if hasattr(completed, "isoformat") else str(completed or "")
    lines = [
        f"Count: {report['count_number']}  Warehouse: {report['warehouse_code']} — {report['warehouse_name']}",
        f"Completed: {completed_s}",
        (
            f"Lines: {report['line_count']}  With variance: {report['variance_line_count']}  "
            f"Qty var: {report['total_variance_qty']}  Value var: {report['total_variance_value']}"
        ),
        "",
        "SKU | Expected | Counted | Var Qty | Var Value",
    ]
    for row in report["rows"]:
        if abs(float(row["variance_qty"])) < 1e-9:
            continue
        lines.append(
            f"{row['sku']} | {row['expected_qty']} | {row['counted_qty']} | "
            f"{row['variance_qty']} | {row['variance_value']}"
        )
    if report["variance_line_count"] == 0:
        lines.append("(no quantity variances)")
    return to_pdf(
        "Stock Count Variance Report",
        lines,
        subtitle=report["count_number"],
    )
