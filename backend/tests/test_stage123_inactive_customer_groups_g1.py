"""Stage 123 G1 — inactive customer groups honesty (?is_active=false)."""

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
async def test_customer_groups_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "Soon Inactive Group 123", "discount_percent": 5},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/customers/groups/{gid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/customers/groups?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == gid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/customers/groups?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == gid for r in active.json()["data"])

    active_only = await ac.get("/api/v1/customers/groups?active_only=true", headers=headers)
    assert active_only.status_code == 200, active_only.text
    assert not any(r["id"] == gid for r in active_only.json()["data"])


def test_shell_and_sales_inactive_customer_groups_g1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "group_active=false" in shell
    assert "Inactive Customer Groups" in shell
    assert "Active Customer Groups" in shell
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 123" in page
    assert "group_active" in page
    assert "groupActiveFilter" in page
