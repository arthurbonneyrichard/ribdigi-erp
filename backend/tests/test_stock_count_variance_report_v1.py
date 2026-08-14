"""Stock count variance report (BR-5.2)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stores import create_store
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_stock_count_variance_report_and_export(client, db_session):
    ac, seed = client
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
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
    count = created.json()["data"]

    patched = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count['id']}/items",
        headers=headers,
        json={"items": [{"product_id": seed["p1"].id, "counted_qty": 7}]},
    )
    assert patched.status_code == 200, patched.text

    done = await ac.post(
        f"/api/v1/inventory/stock-counts/{count['id']}/complete",
        headers=headers,
    )
    assert done.status_code == 200, done.text

    report = await ac.get(
        f"/api/v1/reports/inventory/stock-counts?warehouse_id={wh.id}&variance_only=true",
        headers=headers,
    )
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    assert data["count_sessions"] >= 1
    assert data["lines_with_variance"] >= 1
    assert data["total_variance_qty"] == -3
    assert data["variance_only"] is True
    assert any(line["variance"] == -3 for line in data["lines"])
    assert all(abs(float(line["variance"] or 0)) > 1e-9 for line in data["lines"])

    include_zero = await ac.get(
        f"/api/v1/reports/inventory/stock-counts?warehouse_id={wh.id}&variance_only=false",
        headers=headers,
    )
    assert include_zero.status_code == 200, include_zero.text

    # Admin has reports:read (mgr may too via store manager role — use super for export)
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    export = await ac.get(
        f"/api/v1/reports/export?report_type=inventory_stock_counts&format=csv"
        f"&warehouse_id={wh.id}",
        headers=admin,
    )
    assert export.status_code == 200, export.text
    assert "text/csv" in export.headers.get("content-type", "")
    body = export.text
    assert "variance" in body.lower() or seed["p1"].sku in body or count["count_number"] in body
