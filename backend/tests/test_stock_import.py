"""Stock-only CSV import for existing products."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app import models as m
from app.stock_import import template_csv
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_stock_csv_adjust_and_set(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    tmpl = await ac.get("/api/v1/inventory/stock/import/template", headers=headers)
    assert tmpl.status_code == 200
    assert "sku,barcode,warehouse_code,quantity,mode,reason" in tmpl.text
    assert template_csv().startswith("sku,barcode")

    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 10
    product.barcode = "96385074"
    await db_session.commit()

    csv_body = (
        "sku,barcode,warehouse_code,quantity,mode,reason\n"
        "A-1,,,-3,adjust,Damage write-off\n"
        ",96385074,,20,set,Cycle count set\n"
        "MISSING,,,1,adjust,Bad sku\n"
    )
    dry = await ac.post(
        "/api/v1/inventory/stock/import?dry_run=true",
        headers=headers,
        files={"file": ("stock.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    data = dry.json()["data"]
    assert data["dry_run"] is True
    assert data["valid_rows"] == 2
    assert data["error_rows"] == 1
    assert data["applied"] == []
    # Sequential: adjust -3 from 10, then set 20 from 7 => +13
    assert data["preview"][0]["delta"] == -3
    assert data["preview"][1]["delta"] == 13

    # After dry-run stock unchanged
    await db_session.refresh(product)
    assert float(product.stock_qty) == 10

    committed = await ac.post(
        "/api/v1/inventory/stock/import?dry_run=false",
        headers=headers,
        files={"file": ("stock.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()["data"]
    assert result["valid_rows"] == 2
    assert len(result["applied"]) == 2

    await db_session.refresh(product)
    assert float(product.stock_qty) == 20

    movements = list(
        (
            await db_session.execute(
                select(m.StockMovement)
                .where(
                    m.StockMovement.tenant_id == seed["t1"].id,
                    m.StockMovement.product_id == product.id,
                    m.StockMovement.reference_type == "stock_import",
                )
                .order_by(m.StockMovement.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert len(movements) == 2
    assert float(movements[0].quantity) == -3
    assert movements[0].movement_type == "adjustment"
    assert float(movements[1].quantity) == 13
    assert movements[1].movement_type == "adjustment"


@pytest.mark.asyncio
async def test_stock_csv_warehouse_set(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id

    wh = m.Warehouse(tenant_id=tenant_id, name="Main WH", code="MAIN")
    db_session.add(wh)
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 5
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=tenant_id,
            warehouse_id=wh.id,
            product_id=product.id,
            quantity=5,
        )
    )
    await db_session.commit()

    csv_body = (
        "sku,barcode,warehouse_code,quantity,mode,reason\n"
        f"{product.sku},,MAIN,12,set,Warehouse opening\n"
    )
    committed = await ac.post(
        "/api/v1/inventory/stock/import?dry_run=false",
        headers=headers,
        files={"file": ("stock.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["data"]["valid_rows"] == 1

    await db_session.refresh(product)
    assert float(product.stock_qty) == 12
    wh_stock = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == product.id,
            )
        )
    ).scalar_one()
    assert float(wh_stock.quantity) == 12
