"""Physical stock counts and purchase-request → PO conversion."""

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _admin_headers(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_count_adjusts_warehouse_and_product_qty(client):
    ac, seeded = client
    headers = await _admin_headers(ac, seeded)
    product_id = seeded["p1"].id

    wh = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Count WH", "code": "CNT-WH"},
    )
    assert wh.status_code == 200, wh.text
    warehouse_id = wh.json()["data"]["id"]

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product_id, "quantity": 10, "warehouse_id": warehouse_id},
    )
    assert stock_in.status_code == 200, stock_in.text

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": warehouse_id, "product_ids": [product_id]},
    )
    assert created.status_code == 200, created.text
    count = created.json()["data"]
    assert count["status"] == "draft"
    assert count["item_count"] == 1
    item = count["items"][0]
    assert item["expected_qty"] == 20

    started = await ac.post(
        f"/api/v1/inventory/stock-counts/{count['id']}/start",
        headers=headers,
        json={},
    )
    assert started.status_code == 200, started.text
    assert started.json()["data"]["status"] == "in_progress"

    updated = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count['id']}/items/{item['id']}",
        headers=headers,
        json={"actual_qty": 7, "notes": "shelf short"},
    )
    assert updated.status_code == 200, updated.text
    line = updated.json()["data"]["items"][0]
    assert line["actual_qty"] == 7
    assert line["difference"] == -13

    done = await ac.post(
        f"/api/v1/inventory/stock-counts/{count['id']}/complete",
        headers=headers,
        json={"treat_uncounted_as_expected": False},
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"
    assert done.json()["data"]["variance_item_count"] == 1

    products = await ac.get("/api/v1/products", headers=headers)
    row = next(p for p in products.json()["data"] if p["id"] == product_id)
    assert row["stock_qty"] == 7

    movements = await ac.get("/api/v1/inventory/movements", headers=headers)
    types = {mv["movement_type"] for mv in movements.json()["data"]}
    assert "stock_count" in types


@pytest.mark.asyncio
async def test_stock_count_is_tenant_scoped(client):
    ac, seeded = client
    alpha = await _admin_headers(ac, seeded)
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    wh = await ac.post(
        "/api/v1/warehouses",
        headers=alpha,
        json={"name": "Alpha Count WH", "code": "A-CNT"},
    )
    warehouse_id = wh.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=alpha,
        json={"warehouse_id": warehouse_id, "product_ids": [seeded["p1"].id]},
    )
    count_id = created.json()["data"]["id"]

    foreign = await ac.get(f"/api/v1/inventory/stock-counts/{count_id}", headers=beta)
    assert foreign.status_code == 404

    listed = await ac.get("/api/v1/inventory/stock-counts", headers=beta)
    assert listed.status_code == 200
    assert listed.json()["data"] == []


@pytest.mark.asyncio
async def test_cannot_complete_cancelled_stock_count(client):
    ac, seeded = client
    headers = await _admin_headers(ac, seeded)
    wh = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": "Cancel WH", "code": "CX-WH"},
    )
    warehouse_id = wh.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": warehouse_id, "product_ids": [seeded["p1"].id]},
    )
    count_id = created.json()["data"]["id"]
    cancelled = await ac.post(
        f"/api/v1/inventory/stock-counts/{count_id}/cancel",
        headers=headers,
        json={},
    )
    assert cancelled.status_code == 200
    complete = await ac.post(
        f"/api/v1/inventory/stock-counts/{count_id}/complete",
        headers=headers,
        json={},
    )
    assert complete.status_code == 409


@pytest.mark.asyncio
async def test_purchase_request_approve_convert_creates_po(client):
    ac, seeded = client
    headers = await _admin_headers(ac, seeded)
    product_id = seeded["p1"].id

    supplier = await ac.post("/api/v1/suppliers", headers=headers, json={"name": "Count Supplier"})
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={"notes": "restock", "items": [{"product_id": product_id, "quantity": 12}]},
    )
    assert created.status_code == 200, created.text
    req = created.json()["data"]
    assert req["status"] == "pending"
    assert req["items"][0]["quantity"] == 12

    convert_too_soon = await ac.post(
        f"/api/v1/purchasing/requests/{req['id']}/convert",
        headers=headers,
        json={"supplier_id": supplier_id},
    )
    assert convert_too_soon.status_code == 409

    approved = await ac.post(
        f"/api/v1/purchasing/requests/{req['id']}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"

    converted = await ac.post(
        f"/api/v1/purchasing/requests/{req['id']}/convert",
        headers=headers,
        json={"supplier_id": supplier_id},
    )
    assert converted.status_code == 200, converted.text
    body = converted.json()["data"]
    assert body["request"]["status"] == "converted"
    assert body["purchase_order"]["status"] == "draft"
    assert body["purchase_order"]["supplier_id"] == supplier_id
    assert body["purchase_order"]["items"][0]["quantity"] == 12
    assert body["request"]["converted_po_id"] == body["purchase_order"]["id"]


@pytest.mark.asyncio
async def test_purchase_request_reject_and_tenant_isolation(client, db_session):
    ac, seeded = client
    alpha = await _admin_headers(ac, seeded)

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=alpha,
        json={"items": [{"product_id": seeded["p1"].id, "quantity": 3}]},
    )
    request_id = created.json()["data"]["id"]
    rejected = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/reject",
        headers=alpha,
        json={"reason": "duplicate"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"

    mgr2 = m.User(
        tenant_id=seeded["t2"].id,
        email="mgr@beta.example.com",
        full_name="Beta Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr2)
    await db_session.commit()

    beta = await auth_headers(ac, email="mgr@beta.example.com", tenant_slug="beta")
    foreign = await ac.get(f"/api/v1/purchasing/requests/{request_id}", headers=beta)
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_stock_count_service_skips_zero_variance(db_session, seeded):
    from app import stock_counts as stock_counts_svc

    tenant_id = seeded["t1"].id
    product = seeded["p1"]
    wh = m.Warehouse(tenant_id=tenant_id, name="Zero WH", code="Z-WH")
    db_session.add(wh)
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seeded["admin1"].id,
        warehouse_id=wh.id,
    )
    count = await stock_counts_svc.create_stock_count(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        warehouse_id=wh.id,
        product_ids=[product.id],
    )
    item = (
        await db_session.execute(
            select(m.StockCountItem).where(m.StockCountItem.stock_count_id == count.id)
        )
    ).scalar_one()
    expected = float(item.expected_qty)
    await stock_counts_svc.set_count_item_actual(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        count_id=count.id,
        item_id=item.id,
        actual_qty=expected,
    )
    done = await stock_counts_svc.complete_stock_count(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        count_id=count.id,
    )
    await db_session.commit()
    await db_session.refresh(product)
    assert done.status == "completed"
    assert float(product.stock_qty) == expected
