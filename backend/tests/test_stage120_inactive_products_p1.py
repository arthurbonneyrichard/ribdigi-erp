"""Stage 120 P1 — inactive products honesty (?is_active=false)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_products_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Soon Inactive Widget",
            "sku": "INA-120-001",
            "cost_price": 1.0,
            "selling_price": 2.0,
        },
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/products?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == pid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/products?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert all(r.get("is_active") is not False for r in active.json()["data"])
    assert not any(r["id"] == pid for r in active.json()["data"])

    active_only = await ac.get("/api/v1/products?active_only=true", headers=headers)
    assert active_only.status_code == 200, active_only.text
    assert not any(r["id"] == pid for r in active_only.json()["data"])


def test_shell_and_inventory_inactive_products_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "product_active=false" in shell
    assert "Inactive Products" in shell
    assert "Active Products" in shell
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 120" in inv
    assert "product_active" in inv
    assert "productActiveFilter" in inv
