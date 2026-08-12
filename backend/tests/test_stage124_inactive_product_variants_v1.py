"""Stage 124 V1 — inactive product variants honesty (?is_active=false)."""

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
async def test_product_variants_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product_id = seed["p1"].id

    created = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": "Soon Inactive Var", "sku": "P1-INA124", "size": "M", "selling_price": 9},
    )
    assert created.status_code == 200, created.text
    vid = created.json()["data"]["id"]

    deactivated = await ac.delete(
        f"/api/v1/products/{product_id}/variants/{vid}",
        headers=headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False

    inactive = await ac.get(
        f"/api/v1/products/{product_id}/variants?is_active=false", headers=headers
    )
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == vid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get(
        f"/api/v1/products/{product_id}/variants?is_active=true", headers=headers
    )
    assert active.status_code == 200, active.text
    assert not any(r["id"] == vid for r in active.json()["data"])

    reactivated = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{vid}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["data"]["is_active"] is True


def test_shell_and_inventory_inactive_variants_v1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "variant_active=false" in shell
    assert "Inactive Variants" in shell
    assert "Active Variants" in shell
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 124" in page
    assert "variantActiveFilter" in page
    assert "variant_active" in page
