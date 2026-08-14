"""Brand + UoM Activate and inactive product-assign guards (BR-5.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_brand_uom_activate_ui_wired():
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Brand ${b.name} activated" in inventory
    assert "Unit ${u.code} activated" in inventory
    assert 'JSON.stringify({ is_active: true })' in inventory
    assert "b.is_active !== false" in inventory
    assert "u.is_active !== false" in inventory
    assert "Activate" in inventory
    assert "Deactivate" in inventory


@pytest.mark.asyncio
async def test_inactive_brand_and_unit_blocked_on_product(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=admin,
        json={"code": "DEACT-BR", "name": "Deact Brand Co", "description": "temp"},
    )
    assert brand.status_code == 200, brand.text
    brand_id = brand.json()["data"]["id"]

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=admin,
        json={"code": "DBOX", "name": "Deact Box"},
    )
    assert unit.status_code == 200, unit.text
    unit_id = unit.json()["data"]["id"]

    deact_brand = await ac.delete(f"/api/v1/catalog/brands/{brand_id}", headers=admin)
    assert deact_brand.status_code == 200, deact_brand.text
    assert deact_brand.json()["data"]["is_active"] is False

    deact_unit = await ac.delete(f"/api/v1/catalog/units/{unit_id}", headers=admin)
    assert deact_unit.status_code == 200, deact_unit.text
    assert deact_unit.json()["data"]["is_active"] is False

    bad_brand = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Needs Brand",
            "sku": "NEED-BR-1",
            "selling_price": 5,
            "cost_price": 2,
            "brand_id": brand_id,
        },
    )
    assert bad_brand.status_code == 400, bad_brand.text
    assert "brand" in bad_brand.json()["detail"].lower()
    assert "inactive" in bad_brand.json()["detail"].lower()

    bad_unit = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Needs Unit",
            "sku": "NEED-UN-1",
            "selling_price": 5,
            "cost_price": 2,
            "unit_id": unit_id,
        },
    )
    assert bad_unit.status_code == 400, bad_unit.text
    assert "unit" in bad_unit.json()["detail"].lower()
    assert "inactive" in bad_unit.json()["detail"].lower()

    react_brand = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=admin,
        json={"is_active": True},
    )
    assert react_brand.status_code == 200, react_brand.text
    assert react_brand.json()["data"]["is_active"] is True

    react_unit = await ac.patch(
        f"/api/v1/catalog/units/{unit_id}",
        headers=admin,
        json={"is_active": True},
    )
    assert react_unit.status_code == 200, react_unit.text
    assert react_unit.json()["data"]["is_active"] is True

    ok = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Brand Unit Ok",
            "sku": "BR-UN-OK-1",
            "selling_price": 8,
            "cost_price": 3,
            "brand_id": brand_id,
            "unit_id": unit_id,
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["brand_id"] == brand_id
    assert body["unit_id"] == unit_id
