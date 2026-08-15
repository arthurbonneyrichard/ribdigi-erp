"""Warehouse soft-deactivate — Multi-Store UI + stock/PO inactive guards (BR-2.4)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_warehouse_soft_deactivate_ui_wired():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "setWarehouseActive" in stores
    assert "Warehouse reactivated" in stores or "Warehouse deactivated" in stores
    assert "/warehouses/" in stores
    assert "warehouseManageFilter" in stores
    assert 'aria-label="Warehouse status filter"' in stores
    assert "managedWarehouses" in stores
    assert "branchManageFilter" in stores
    assert 'aria-label="Branch status filter"' in stores
    assert "departmentManageFilter" in stores
    assert 'aria-label="Department status filter"' in stores
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "w.is_active !== false" in inventory


@pytest.mark.asyncio
async def test_warehouses_list_is_active_filter(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={
            "name": "Filter Warehouse Co",
            "code": "FLT-WH",
            "warehouse_type": "retail",
            "address": "9 Filter Dock",
        },
    )
    assert created.status_code == 200, created.text
    wid = created.json()["data"]["id"]

    await ac.patch(
        f"/api/v1/warehouses/{wid}",
        headers=admin,
        json={"is_active": False},
    )

    all_rows = await ac.get("/api/v1/warehouses", headers=admin)
    assert wid in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/warehouses?is_active=true", headers=admin)
    assert wid not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get("/api/v1/warehouses?is_active=false", headers=admin)
    assert wid in {r["id"] for r in inactive_only.json()["data"]}
    assert all(r["is_active"] is False for r in inactive_only.json()["data"])


@pytest.mark.asyncio
async def test_inactive_warehouse_blocked_on_stock_in(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={
            "name": "Deact Warehouse Co",
            "code": "DEACT-WH",
            "warehouse_type": "retail",
            "address": "1 Quiet Dock",
        },
    )
    assert created.status_code == 200, created.text
    wid = created.json()["data"]["id"]
    assert created.json()["data"]["is_active"] is True

    deact = await ac.patch(
        f"/api/v1/warehouses/{wid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    blocked = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={
            "product_id": seed["p1"].id,
            "quantity": 2,
            "warehouse_id": wid,
            "notes": "should fail",
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.json()["detail"].lower()

    react = await ac.patch(
        f"/api/v1/warehouses/{wid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    ok = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={
            "product_id": seed["p1"].id,
            "quantity": 2,
            "warehouse_id": wid,
            "notes": "ok after reactivate",
        },
    )
    assert ok.status_code == 200, ok.text
