"""Product soft-deactivate UI + inactive sale/purchase guards (BR-5.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_product_deactivate_ui_wired():
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "setProductActive" in inventory
    assert "Deactivate" in inventory
    assert "Activate" in inventory
    assert "[inactive]" in inventory
    assert "productManageFilter" in inventory
    assert 'aria-label="Product status filter"' in inventory
    assert "managedProducts" in inventory

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "is_active !== false" in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "is_active !== false" in purchasing


@pytest.mark.asyncio
async def test_products_list_is_active_filter(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Filter Demo Widget",
            "sku": "FLT-WDG-1",
            "selling_price": 4.25,
            "cost_price": 1,
        },
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]

    await ac.patch(
        f"/api/v1/products/{pid}",
        headers=admin,
        json={"is_active": False},
    )

    all_rows = await ac.get("/api/v1/products", headers=admin)
    assert all_rows.status_code == 200
    assert pid in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/products?is_active=true", headers=admin)
    assert active_only.status_code == 200
    assert pid not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get("/api/v1/products?is_active=false", headers=admin)
    assert inactive_only.status_code == 200
    assert pid in {r["id"] for r in inactive_only.json()["data"]}
    assert all(r["is_active"] is False for r in inactive_only.json()["data"])


@pytest.mark.asyncio
async def test_inactive_product_blocked_on_sale_and_reactivates(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Obsolete Widget",
            "sku": "OBS-WDG-1",
            "selling_price": 9.5,
            "cost_price": 3,
        },
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]
    assert created.json()["data"]["is_active"] is True

    deact = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    blocked = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": pid, "quantity": 1}],
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.text.lower()

    pr_blocked = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={"items": [{"product_id": pid, "quantity": 1}]},
    )
    assert pr_blocked.status_code == 400, pr_blocked.text
    assert "inactive" in pr_blocked.text.lower()

    react = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    ok = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": pid, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text
