"""Stage 122 M1 — inactive catalog meta honesty (?is_active=false)."""

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
async def test_categories_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "CATINA122", "name": "Soon Inactive Cat"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/catalog/categories/{cid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/catalog/categories?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == cid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/catalog/categories?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == cid for r in active.json()["data"])


@pytest.mark.asyncio
async def test_brands_and_units_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "BRDINA122", "name": "Soon Inactive Brand"},
    )
    assert brand.status_code == 200, brand.text
    bid = brand.json()["data"]["id"]
    await ac.patch(f"/api/v1/catalog/brands/{bid}", headers=headers, json={"is_active": False})

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "UINA122", "name": "Soon Inactive Unit"},
    )
    assert unit.status_code == 200, unit.text
    uid = unit.json()["data"]["id"]
    await ac.patch(f"/api/v1/catalog/units/{uid}", headers=headers, json={"is_active": False})

    brands_inactive = await ac.get("/api/v1/catalog/brands?is_active=false", headers=headers)
    assert brands_inactive.status_code == 200, brands_inactive.text
    assert any(r["id"] == bid for r in brands_inactive.json()["data"])
    assert all(r.get("is_active") is False for r in brands_inactive.json()["data"])

    units_inactive = await ac.get("/api/v1/catalog/units?is_active=false", headers=headers)
    assert units_inactive.status_code == 200, units_inactive.text
    assert any(r["id"] == uid for r in units_inactive.json()["data"])
    assert all(r.get("is_active") is False for r in units_inactive.json()["data"])

    brands_active = await ac.get("/api/v1/catalog/brands?active_only=true", headers=headers)
    assert brands_active.status_code == 200, brands_active.text
    assert not any(r["id"] == bid for r in brands_active.json()["data"])


def test_shell_and_inventory_inactive_catalog_meta_m1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "category_active=false" in shell
    assert "Inactive Categories" in shell
    assert "brand_active=false" in shell
    assert "Inactive Brands" in shell
    assert "unit_active=false" in shell
    assert "Inactive Units" in shell
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 122" in page
    assert "categoryActiveFilter" in page
    assert "brandActiveFilter" in page
    assert "unitActiveFilter" in page
