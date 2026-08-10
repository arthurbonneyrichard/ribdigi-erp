"""Stage 17 S2: stock count → enter counts → complete posts adjustments → variance report."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _wh_qty(db, tenant_id: str, warehouse_id: str, product_id: str) -> float:
    row = (
        await db.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == warehouse_id,
                m.WarehouseStock.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    return float(row.quantity) if row else 0.0


@pytest.mark.asyncio
async def test_stock_count_complete_posts_adjustments_and_variance_report(client, db_session):
    """Create → patch counts → complete → adjustment movement → variance export; immutable."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 S2 Count SKU",
        sku="S17-S2-CNT",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    wh = m.Warehouse(tenant_id=tenant_id, name="S17 S2 Count WH", code="S17S2WH")
    db_session.add_all([product, wh])
    await db_session.commit()
    product_id, warehouse_id = product.id, wh.id

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 10,
            "warehouse_id": warehouse_id,
            "notes": "S17 S2 seed",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": warehouse_id, "product_ids": [product_id], "notes": "S17 S2 count"},
    )
    assert created.status_code == 200, created.text
    count = created.json()["data"]
    count_id = count["id"]
    assert count["status"] == "draft"
    assert float(count["items"][0]["expected_qty"]) == pytest.approx(10)
    assert count["items"][0]["counted_qty"] is None

    # Draft variance report is blocked (export after complete)
    draft_report = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report",
        headers=headers,
        params={"format": "json"},
    )
    assert draft_report.status_code == 409
    assert draft_report.json()["detail"]["code"] == "COUNT_NOT_COMPLETED"

    patched = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count_id}/items",
        headers=headers,
        json={"items": [{"product_id": product_id, "counted_qty": 7, "notes": "shelf short"}]},
    )
    assert patched.status_code == 200, patched.text
    item = patched.json()["data"]["items"][0]
    assert float(item["counted_qty"]) == pytest.approx(7)
    assert float(item["variance"]) == pytest.approx(-3)

    done = await ac.post(
        f"/api/v1/inventory/stock-counts/{count_id}/complete",
        headers=headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"

    db_session.expire_all()
    assert await _wh_qty(db_session, tenant_id, warehouse_id, product_id) == pytest.approx(7)
    product_row = await db_session.get(m.Product, product_id)
    await db_session.refresh(product_row)
    assert float(product_row.stock_qty) == pytest.approx(7)

    move = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.product_id == product_id,
                m.StockMovement.movement_type == "adjustment",
                m.StockMovement.reference_type == "stock_count",
                m.StockMovement.reference_id == count_id,
            )
        )
    ).scalar_one()
    assert float(move.quantity) == pytest.approx(-3)
    assert move.warehouse_id == warehouse_id

    report = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report",
        headers=headers,
        params={"format": "json"},
    )
    assert report.status_code == 200, report.text
    body = report.json()["data"]
    assert body["count_id"] == count_id
    assert float(body["total_variance_qty"]) == pytest.approx(-3)
    assert body["variance_line_count"] >= 1
    assert any(float(r["variance_qty"]) == pytest.approx(-3) for r in body["rows"])

    csv_report = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report",
        headers=headers,
        params={"format": "csv"},
    )
    assert csv_report.status_code == 200, csv_report.text
    assert "text/csv" in csv_report.headers.get("content-type", "")
    assert "S17-S2-CNT" in csv_report.text or "-3" in csv_report.text

    # Immutable: cannot re-complete
    again = await ac.post(
        f"/api/v1/inventory/stock-counts/{count_id}/complete",
        headers=headers,
    )
    assert again.status_code == 409

    # Cancel path on a fresh draft
    created2 = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": warehouse_id, "product_ids": [product_id]},
    )
    assert created2.status_code == 200, created2.text
    cid2 = created2.json()["data"]["id"]
    cancelled = await ac.post(f"/api/v1/inventory/stock-counts/{cid2}/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    patch_cancelled = await ac.patch(
        f"/api/v1/inventory/stock-counts/{cid2}/items",
        headers=headers,
        json={"items": [{"product_id": product_id, "counted_qty": 1}]},
    )
    assert patch_cancelled.status_code == 409


def test_inventory_ui_surfaces_stock_counts():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "'counts'" in page or "Stock counts" in page
    assert "/inventory/stock-counts" in page
    assert "variance-report" in page
    assert "complete" in page.lower()


def test_stock_count_s2_docs():
    plan = (ROOT / "docs/STAGE_17_PLAN.md").read_text(encoding="utf-8")
    assert "| **S2**" in plan
    assert "test_stock_count_chain_s2.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 17 S2" in br
    assert "[x] **Stock Count:**" in br
