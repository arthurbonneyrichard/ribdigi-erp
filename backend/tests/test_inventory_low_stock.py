"""Manage Stock / warehouse-stock low vs out-of-stock (location or product floor)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _wh(db_session, tenant_id: str, *, code: str, name: str) -> m.Warehouse:
    store = m.Store(tenant_id=tenant_id, code=f"S-{code}", name=f"{name} store", is_active=True)
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        code=code,
        name=name,
        is_active=True,
    )
    db_session.add(wh)
    await db_session.flush()
    return wh


async def _product(db_session, tenant_id: str, *, sku: str, name: str, **kwargs) -> m.Product:
    p = m.Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        cost_price=1,
        selling_price=2,
        stock_qty=kwargs.pop("stock_qty", 0),
        is_active=True,
        **kwargs,
    )
    db_session.add(p)
    await db_session.flush()
    return p


def test_manage_stock_low_filter_ui_empty_vs_error():
    inv = (ROOT / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    assert "warehouseRowIsLow" in inv
    assert "Clear the low-stock filter or pick another location when nothing is low here." in inv
    assert 'aria-label="Retry warehouse stock"' in inv
    assert "Could not load stock for this location." in inv
    assert "whStockFailed" in inv
    failed_idx = inv.index("Could not load stock for this location.")
    receive_idx = inv.index("Receive stock into this location")
    retry_idx = inv.index('aria-label="Retry warehouse stock"')
    assert retry_idx < receive_idx
    assert failed_idx < receive_idx
    assert "/inventory/warehouse-stock" in inv
    assert "/inventory/low-stock" in inv


@pytest.mark.asyncio
async def test_warehouse_stock_low_vs_oos_product_and_location_floor(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    user_id = seed["super"].id
    wh_a = await _wh(db_session, tenant_id, code="LS-A", name="Low A")
    wh_b = await _wh(db_session, tenant_id, code="LS-B", name="Low B")

    above = await _product(
        db_session, tenant_id, sku="LS-ABOVE", name="Above floor", reorder_level=10
    )
    at_floor = await _product(
        db_session, tenant_id, sku="LS-AT", name="At floor", reorder_level=10
    )
    below = await _product(
        db_session, tenant_id, sku="LS-BELOW", name="Below floor", reorder_level=10
    )
    zero_bal = await _product(
        db_session, tenant_id, sku="LS-ZERO", name="Zero with floor", reorder_level=10
    )
    missing = await _product(
        db_session, tenant_id, sku="LS-MISS", name="Missing balance", reorder_level=10
    )
    loc_min = await _product(
        db_session, tenant_id, sku="LS-MIN", name="Location min", reorder_level=0, minimum_stock=0
    )
    loc_over = await _product(
        db_session, tenant_id, sku="LS-OVER", name="Location overrides", reorder_level=2
    )

    for product, qty, warehouse_id in (
        (above, 20, wh_a.id),
        (at_floor, 10, wh_a.id),
        (below, 3, wh_a.id),
        (loc_min, 4, wh_a.id),
        (loc_over, 10, wh_a.id),
        (below, 15, wh_b.id),
        (at_floor, 4, wh_b.id),
    ):
        await apply_stock_change(
            db_session,
            tenant_id=tenant_id,
            product_id=product.id,
            quantity_delta=qty,
            movement_type="stock_in",
            user_id=user_id,
            warehouse_id=warehouse_id,
            allow_negative=False,
        )

    db_session.add(
        m.WarehouseStock(
            tenant_id=tenant_id,
            warehouse_id=wh_a.id,
            product_id=zero_bal.id,
            quantity=0,
            reorder_level=10,
        )
    )
    await db_session.flush()

    for row in (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == wh_a.id,
                m.WarehouseStock.product_id.in_([loc_min.id, loc_over.id]),
            )
        )
    ).scalars().all():
        if row.product_id == loc_min.id:
            row.minimum_stock = 8
            row.reorder_level = 0
        elif row.product_id == loc_over.id:
            row.reorder_level = 20
    await db_session.commit()

    listed = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_a.id}&include_zero=true",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    by = {i["product_id"]: i for i in listed.json()["data"]["items"]}

    assert missing.id in by
    assert float(by[missing.id]["quantity"]) == 0
    assert by[missing.id]["is_out_of_stock"] is True
    assert by[missing.id]["below_reorder"] is False
    assert by[missing.id]["is_low_stock"] is False
    assert by[missing.id]["stock_status"] == "out"

    assert by[zero_bal.id]["is_out_of_stock"] is True
    assert by[zero_bal.id]["below_reorder"] is False

    assert by[above.id]["below_reorder"] is False
    assert by[above.id]["is_low_stock"] is False
    assert by[above.id]["stock_status"] != "red"

    assert by[at_floor.id]["below_reorder"] is True
    assert by[at_floor.id]["is_low_stock"] is True
    assert float(by[at_floor.id]["low_stock_floor"]) == 10

    assert by[below.id]["below_reorder"] is True
    assert float(by[below.id]["quantity"]) == 3
    assert float(by[below.id]["product_reorder_level"]) == 10

    assert by[loc_min.id]["below_reorder"] is True
    assert float(by[loc_min.id]["low_stock_floor"]) == 8

    assert by[loc_over.id]["below_reorder"] is True
    assert float(by[loc_over.id]["low_stock_floor"]) == 20

    hidden = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert hidden.status_code == 200
    hidden_ids = {i["product_id"] for i in hidden.json()["data"]["items"]}
    assert missing.id not in hidden_ids
    assert below.id in hidden_ids
    assert at_floor.id in hidden_ids

    other = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_b.id}&include_zero=true",
        headers=headers,
    )
    assert other.status_code == 200, other.text
    b_items = {i["product_id"]: i for i in other.json()["data"]["items"]}
    assert b_items[below.id]["below_reorder"] is False
    assert float(b_items[below.id]["quantity"]) == 15
    assert b_items[at_floor.id]["below_reorder"] is True
    assert float(b_items[at_floor.id]["quantity"]) == 4

    low_report = await ac.get(
        f"/api/v1/inventory/low-stock?store_id={wh_a.store_id}",
        headers=headers,
    )
    assert low_report.status_code == 200, low_report.text
    wh_low_ids = {r["product_id"] for r in low_report.json()["data"]["warehouse_low_stock"]}
    assert below.id in wh_low_ids
    assert at_floor.id in wh_low_ids
    assert loc_min.id in wh_low_ids
    assert loc_over.id in wh_low_ids
    assert above.id not in wh_low_ids
    assert missing.id not in wh_low_ids
    assert zero_bal.id not in wh_low_ids


@pytest.mark.asyncio
async def test_warehouse_stock_tenant_and_assigned_location(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    wh_ok = await _wh(db_session, tenant_id, code="LS-OK", name="Allowed WH")
    wh_deny = await _wh(db_session, tenant_id, code="LS-NO", name="Denied WH")
    beta_admin = m.User(
        tenant_id=seed["t2"].id,
        email=f"admin-{uuid4().hex[:8]}@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
    )
    db_session.add(beta_admin)
    await db_session.commit()

    assigned = await ac.put(
        f"/api/v1/users/{seed['mgr1'].id}/stores",
        headers=headers,
        json={"store_ids": [wh_ok.store_id]},
    )
    assert assigned.status_code == 200, assigned.text
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    ok = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_ok.id}&include_zero=true",
        headers=mgr,
    )
    assert ok.status_code == 200, ok.text

    denied = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_deny.id}&include_zero=true",
        headers=mgr,
    )
    assert denied.status_code == 403, denied.text

    beta = await auth_headers(ac, email=beta_admin.email, tenant_slug="beta")
    other = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={wh_ok.id}&include_zero=true",
        headers=beta,
    )
    assert other.status_code == 404, other.text
