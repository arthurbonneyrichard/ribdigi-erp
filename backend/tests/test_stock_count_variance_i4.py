"""Stage 2 I4: stock count variance report export (BR-5.2)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stores import create_store
from tests.conftest import auth_headers


async def _complete_count_with_variance(ac, db_session, seed):
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    product.cost_price = 2.5
    await db_session.commit()

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Var Report Store", code="VRS"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=10,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh.id, "product_ids": [seed["p1"].id]},
    )
    assert created.status_code == 200, created.text
    count_id = created.json()["data"]["id"]
    count_number = created.json()["data"]["count_number"]

    patched = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count_id}/items",
        headers=headers,
        json={"items": [{"product_id": seed["p1"].id, "counted_qty": 7}]},
    )
    assert patched.status_code == 200, patched.text

    done = await ac.post(
        f"/api/v1/inventory/stock-counts/{count_id}/complete",
        headers=headers,
    )
    assert done.status_code == 200, done.text
    return headers, count_id, count_number, wh


@pytest.mark.asyncio
async def test_variance_report_csv_pdf_and_json(client, db_session):
    ac, seed = client
    headers, count_id, count_number, wh = await _complete_count_with_variance(ac, db_session, seed)

    draft_block = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report?format=csv",
        headers=await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha"),
    )
    # already completed — CSV should succeed
    assert draft_block.status_code == 200, draft_block.text
    assert "text/csv" in draft_block.headers.get("content-type", "")
    csv_text = draft_block.text
    assert "sku" in csv_text
    assert "variance_qty" in csv_text
    assert seed["p1"].sku in csv_text
    assert "-3" in csv_text or "-3.0" in csv_text

    pdf = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report?format=pdf",
        headers=headers,
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers.get("content-type", "").startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"
    assert count_number.encode() in pdf.content or b"Variance" in pdf.content

    js = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report?format=json",
        headers=headers,
    )
    assert js.status_code == 200, js.text
    report = js.json()["data"]
    assert report["count_number"] == count_number
    assert report["warehouse_id"] == wh.id
    assert report["variance_line_count"] == 1
    assert float(report["total_variance_qty"]) == -3
    assert float(report["total_variance_value"]) == -7.5  # -3 * 2.5
    row = report["rows"][0]
    assert float(row["expected_qty"]) == 10
    assert float(row["counted_qty"]) == 7
    assert float(row["variance_qty"]) == -3
    assert float(row["unit_cost"]) == 2.5


@pytest.mark.asyncio
async def test_variance_report_requires_completed(client, db_session):
    ac, seed = client
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    await db_session.commit()
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Draft Var Store", code="DVS"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh.id, "product_ids": [seed["p1"].id]},
    )
    count_id = created.json()["data"]["id"]
    r = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report?format=csv",
        headers=headers,
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "COUNT_NOT_COMPLETED"

    foreign = await ac.get(
        f"/api/v1/inventory/stock-counts/{count_id}/variance-report?format=csv",
        headers=await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta"),
    )
    assert foreign.status_code in {401, 403, 404}
