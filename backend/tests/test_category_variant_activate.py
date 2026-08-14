"""Category + variant Activate (BR-5.1 catalog soft-reactivate)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_category_variant_activate_ui_wired():
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Category ${c.code} activated" in inventory
    assert "activateVariant" in inventory
    assert "Variant activated" in inventory
    assert 'JSON.stringify({ is_active: true })' in inventory
    assert "Activate" in inventory
    assert "Deactivate" in inventory


@pytest.mark.asyncio
async def test_category_and_variant_activate_round_trip(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=admin,
        json={"code": "DEACT-CAT", "name": "Deact Category"},
    )
    assert cat.status_code == 200, cat.text
    cat_id = cat.json()["data"]["id"]

    deact_cat = await ac.delete(f"/api/v1/catalog/categories/{cat_id}", headers=admin)
    assert deact_cat.status_code == 200, deact_cat.text
    assert deact_cat.json()["data"]["is_active"] is False

    blocked = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Needs Cat",
            "sku": "NEED-CAT-1",
            "selling_price": 5,
            "cost_price": 2,
            "category_id": cat_id,
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.json()["detail"].lower()

    react_cat = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=admin,
        json={"is_active": True},
    )
    assert react_cat.status_code == 200, react_cat.text
    assert react_cat.json()["data"]["is_active"] is True

    product = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Variant Host",
            "sku": "VAR-HOST-1",
            "selling_price": 12,
            "cost_price": 4,
            "category_id": cat_id,
        },
    )
    assert product.status_code == 200, product.text
    pid = product.json()["data"]["id"]

    variant = await ac.post(
        f"/api/v1/products/{pid}/variants",
        headers=admin,
        json={"name": "Deact Variant", "sku": "VAR-DEACT-1", "selling_price": 12, "size": "L"},
    )
    assert variant.status_code == 200, variant.text
    vid = variant.json()["data"]["id"]
    assert variant.json()["data"]["is_active"] is True

    deact_var = await ac.delete(
        f"/api/v1/products/{pid}/variants/{vid}", headers=admin
    )
    assert deact_var.status_code == 200, deact_var.text
    assert deact_var.json()["data"]["is_active"] is False

    react_var = await ac.patch(
        f"/api/v1/products/{pid}/variants/{vid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react_var.status_code == 200, react_var.text
    assert react_var.json()["data"]["is_active"] is True
