"""Customer group soft-deactivate + discount edit UI (BR-7.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_customer_group_deactivate_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "setGroupActive" in sales
    assert "saveGroupDiscount" in sales
    assert "Deactivate" in sales
    assert "Activate" in sales
    assert "[inactive]" in sales
    assert "Save discount" in sales
    assert "groupManageFilter" in sales
    assert 'aria-label="Customer group status filter"' in sales
    assert "managedGroups" in sales


@pytest.mark.asyncio
async def test_customer_groups_list_is_active_filter(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/customers/groups",
        headers=admin,
        json={"name": "Filter Demo Club", "discount_percent": 5},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["data"]["id"]

    await ac.patch(
        f"/api/v1/customers/groups/{gid}",
        headers=admin,
        json={"is_active": False},
    )

    all_rows = await ac.get("/api/v1/customers/groups", headers=admin)
    assert gid in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/customers/groups?is_active=true", headers=admin)
    assert gid not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get("/api/v1/customers/groups?is_active=false", headers=admin)
    assert gid in {r["id"] for r in inactive_only.json()["data"]}
    assert all(r["is_active"] is False for r in inactive_only.json()["data"])


@pytest.mark.asyncio
async def test_inactive_group_blocked_on_assign_and_reactivates(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/customers/groups",
        headers=admin,
        json={"name": "Legacy Club", "discount_percent": 8},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["data"]["id"]

    disc = await ac.patch(
        f"/api/v1/customers/groups/{gid}",
        headers=admin,
        json={"discount_percent": 12},
    )
    assert disc.status_code == 200, disc.text
    assert float(disc.json()["data"]["discount_percent"]) == 12.0

    deact = await ac.patch(
        f"/api/v1/customers/groups/{gid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    blocked = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Should Fail", "customer_group_id": gid},
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.text.lower()

    patch_blocked = await ac.patch(
        f"/api/v1/customers/{seed['party1'].id}",
        headers=admin,
        json={"customer_group_id": gid},
    )
    assert patch_blocked.status_code == 400, patch_blocked.text
    assert "inactive" in patch_blocked.text.lower()

    react = await ac.patch(
        f"/api/v1/customers/groups/{gid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    ok = await ac.patch(
        f"/api/v1/customers/{seed['party1'].id}",
        headers=admin,
        json={"customer_group_id": gid},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["customer_group"]["id"] == gid
