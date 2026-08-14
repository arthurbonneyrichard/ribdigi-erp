"""Tax rate soft-deactivate UI + inactive assign/default guards (BR-12.1 / BR-2.8)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tax_rate_deactivate_ui_wired():
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "setRateActive" in tax
    assert "Deactivate" in tax
    assert "Activate" in tax
    assert "/tax/rates/" in tax
    assert "is_active" in tax


@pytest.mark.asyncio
async def test_inactive_tax_rate_blocked_on_category_and_default(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/tax/rates",
        headers=admin,
        json={
            "name": "Obsolete VAT",
            "rate": 7.5,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": False,
            "is_active": True,
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    deact = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False
    assert deact.json()["data"]["is_default"] is False

    default_blocked = await ac.post(f"/api/v1/tax/rates/{rid}/default", headers=admin)
    assert default_blocked.status_code == 400, default_blocked.text
    assert "inactive" in default_blocked.text.lower()

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=admin,
        json={"code": "OLDTAX", "name": "Old Tax Cat", "tax_rate_id": rid},
    )
    assert cat.status_code == 400, cat.text
    assert "inactive" in cat.text.lower()

    react = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    cat_ok = await ac.post(
        "/api/v1/catalog/categories",
        headers=admin,
        json={"code": "NEWTAX", "name": "New Tax Cat", "tax_rate_id": rid},
    )
    assert cat_ok.status_code == 200, cat_ok.text
    assert cat_ok.json()["data"]["tax_rate_id"] == rid

    # Deactivating a default rate clears the default flag
    await ac.post(f"/api/v1/tax/rates/{rid}/default", headers=admin)
    deact_default = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact_default.status_code == 200
    assert deact_default.json()["data"]["is_active"] is False
    assert deact_default.json()["data"]["is_default"] is False
