"""Low-stock purchase suggestions → draft purchase requests."""

from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import purchase_requests as purchase_requests_svc
from app import reports as reports_svc


def _product_suggested_qty(*, stock_qty: float, reorder_level: float, reorder_qty: float = 0) -> float:
    gap = max(0.0, round(float(reorder_level) - float(stock_qty), 3))
    rq = float(reorder_qty or 0)
    if rq > 0:
        return max(rq, gap) if gap > 0 or float(stock_qty) <= float(reorder_level) else 0.0
    return max(1.0, gap) if float(stock_qty) <= float(reorder_level) else 0.0


async def _preferred_suppliers_for_products(
    db: AsyncSession, tenant_id: str, product_ids: list[str]
) -> dict[str, str]:
    """Map product_id → supplier_id from the most recent non-cancelled PO containing that product."""
    if not product_ids:
        return {}
    rows = (
        await db.execute(
            select(m.PurchaseOrderItem.product_id, m.PurchaseOrder.supplier_id, m.PurchaseOrder.created_at)
            .join(m.PurchaseOrder, m.PurchaseOrder.id == m.PurchaseOrderItem.purchase_order_id)
            .where(
                m.PurchaseOrderItem.tenant_id == tenant_id,
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.status != "cancelled",
                m.PurchaseOrderItem.product_id.in_(product_ids),
            )
            .order_by(m.PurchaseOrder.created_at.desc())
        )
    ).all()
    out: dict[str, str] = {}
    for product_id, supplier_id, _created in rows:
        if product_id not in out and supplier_id:
            out[product_id] = supplier_id
    return out


async def _open_pr_product_ids(db: AsyncSession, tenant_id: str) -> set[str]:
    rows = (
        await db.execute(
            select(m.PurchaseRequestItem.product_id)
            .join(m.PurchaseRequest, m.PurchaseRequest.id == m.PurchaseRequestItem.purchase_request_id)
            .where(
                m.PurchaseRequestItem.tenant_id == tenant_id,
                m.PurchaseRequest.tenant_id == tenant_id,
                m.PurchaseRequest.status.in_(("draft", "pending", "approved")),
            )
        )
    ).all()
    return {r[0] for r in rows if r[0]}


async def list_low_stock_suggestions(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_id: str | None = None,
    warehouse_id: str | None = None,
    include_open: bool = False,
) -> dict:
    report = await reports_svc.inventory_low_stock(
        db, tenant_id, store_id=store_id, warehouse_id=warehouse_id
    )
    open_ids = set() if include_open else await _open_pr_product_ids(db, tenant_id)

    lines: list[dict] = []
    # Prefer warehouse-scoped rows when present; also include product-level gaps
    # not already covered by a warehouse row for the same product.
    covered: set[str] = set()
    for row in report.get("warehouse_low_stock") or []:
        pid = row["product_id"]
        covered.add(pid)
        qty = float(row.get("suggested_order_qty") or 0)
        if qty <= 0:
            continue
        lines.append(
            {
                "product_id": pid,
                "sku": row.get("sku"),
                "name": row.get("name"),
                "scope": "warehouse",
                "stock_qty": float(row.get("quantity") or 0),
                "reorder_level": float(row.get("reorder_level") or 0),
                "reorder_qty": float(row.get("reorder_qty") or 0),
                "suggested_order_qty": qty,
                "warehouse_id": row.get("warehouse_id"),
                "warehouse_name": row.get("warehouse_name"),
                "store_id": row.get("store_id"),
                "on_open_pr": pid in open_ids,
            }
        )

    for row in report.get("products") or []:
        pid = row["id"]
        if pid in covered:
            continue
        stock = float(row.get("stock_qty") or 0)
        reorder = float(row.get("reorder_level") or 0)
        qty = _product_suggested_qty(stock_qty=stock, reorder_level=reorder)
        if qty <= 0:
            continue
        lines.append(
            {
                "product_id": pid,
                "sku": row.get("sku"),
                "name": row.get("name"),
                "scope": "product",
                "stock_qty": stock,
                "reorder_level": reorder,
                "reorder_qty": 0.0,
                "suggested_order_qty": qty,
                "warehouse_id": None,
                "warehouse_name": None,
                "store_id": None,
                "on_open_pr": pid in open_ids,
            }
        )

    suppliers = await _preferred_suppliers_for_products(
        db, tenant_id, [ln["product_id"] for ln in lines]
    )
    for ln in lines:
        ln["preferred_supplier_id"] = suppliers.get(ln["product_id"])

    actionable = [ln for ln in lines if include_open or not ln["on_open_pr"]]
    return {
        "count": len(actionable),
        "total_candidates": len(lines),
        "lines": actionable if not include_open else lines,
        "skipped_open_pr": [ln for ln in lines if ln["on_open_pr"]] if not include_open else [],
        "store_id": report.get("store_id"),
        "warehouse_id": report.get("warehouse_id"),
        "store_name": report.get("store_name"),
    }


async def create_requests_from_low_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    lines: list[dict],
    notes: str | None = None,
    department: str | None = None,
    include_open: bool = False,
) -> dict:
    if not lines:
        raise HTTPException(status_code=400, detail="Select at least one suggestion line")

    open_ids = set() if include_open else await _open_pr_product_ids(db, tenant_id)
    skipped: list[dict] = []
    prepared: list[dict] = []

    for raw in lines:
        product_id = raw.get("product_id")
        if not product_id:
            skipped.append({"product_id": None, "reason": "missing_product_id"})
            continue
        if product_id in open_ids:
            skipped.append({"product_id": product_id, "reason": "already_on_open_pr"})
            continue
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == product_id,
                    m.Product.tenant_id == tenant_id,
                    m.Product.is_active == True,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if not product:
            skipped.append({"product_id": product_id, "reason": "product_not_found"})
            continue

        qty = float(raw.get("quantity") or 0)
        warehouse_id = raw.get("warehouse_id") or None
        if qty <= 0:
            # Derive from current stock / warehouse policy
            if warehouse_id:
                stock = (
                    await db.execute(
                        select(m.WarehouseStock).where(
                            m.WarehouseStock.tenant_id == tenant_id,
                            m.WarehouseStock.warehouse_id == warehouse_id,
                            m.WarehouseStock.product_id == product_id,
                        )
                    )
                ).scalar_one_or_none()
                if stock:
                    qty = max(
                        float(stock.reorder_qty or 0),
                        round(float(stock.reorder_level or 0) - float(stock.quantity or 0), 3),
                    )
            if qty <= 0:
                qty = _product_suggested_qty(
                    stock_qty=float(product.stock_qty or 0),
                    reorder_level=float(product.reorder_level or 0),
                )
        if qty <= 0:
            skipped.append({"product_id": product_id, "reason": "quantity_not_positive"})
            continue

        preferred = raw.get("preferred_supplier_id") or None
        if preferred is None:
            prefs = await _preferred_suppliers_for_products(db, tenant_id, [product_id])
            preferred = prefs.get(product_id)

        if warehouse_id:
            wh = (
                await db.execute(
                    select(m.Warehouse).where(
                        m.Warehouse.id == warehouse_id,
                        m.Warehouse.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if not wh:
                skipped.append({"product_id": product_id, "reason": "warehouse_not_found"})
                continue

        prepared.append(
            {
                "product_id": product_id,
                "quantity": qty,
                "warehouse_id": warehouse_id,
                "preferred_supplier_id": preferred,
                "notes": raw.get("notes"),
            }
        )

    if not prepared:
        raise HTTPException(
            status_code=400,
            detail={"message": "No lines eligible for draft PR", "skipped": skipped},
        )

    groups: dict[tuple[str | None, str | None], list[dict]] = defaultdict(list)
    for item in prepared:
        key = (item.get("warehouse_id"), item.get("preferred_supplier_id"))
        groups[key].append(item)

    created_rows: list[m.PurchaseRequest] = []
    for (warehouse_id, preferred_supplier_id), group_items in groups.items():
        row = await purchase_requests_svc.create_request(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            preferred_supplier_id=preferred_supplier_id,
            warehouse_id=warehouse_id,
            department=department,
            notes=notes or "Created from low-stock suggestions",
            items=[
                {
                    "product_id": i["product_id"],
                    "quantity": i["quantity"],
                    "notes": i.get("notes"),
                }
                for i in group_items
            ],
        )
        created_rows.append(row)

    return {
        "created": [await purchase_requests_svc.serialize_request(db, r) for r in created_rows],
        "skipped": skipped,
        "created_count": len(created_rows),
    }


async def create_requests_from_predictions(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    at_risk_lines: list[dict],
    notes: str | None = None,
    min_confidence: float = 0.0,
) -> dict:
    """Turn AI low-stock prediction rows into draft PRs (BR-21.4 auto-suggestions)."""
    lines: list[dict] = []
    for raw in at_risk_lines or []:
        conf = float(raw.get("confidence") or 0)
        if conf < float(min_confidence or 0):
            continue
        qty = float(raw.get("suggested_order_qty") or raw.get("recommended_order_qty") or 0)
        if qty <= 0:
            continue
        lines.append(
            {
                "product_id": raw.get("product_id"),
                "quantity": qty,
                "warehouse_id": raw.get("warehouse_id"),
                "preferred_supplier_id": raw.get("preferred_supplier_id"),
                "notes": raw.get("notes")
                or f"AI prediction ({raw.get('risk_reason') or 'at_risk'}); conf={conf}",
            }
        )
    return await create_requests_from_low_stock(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        lines=lines,
        notes=notes or "Created from AI low-stock predictions",
    )
