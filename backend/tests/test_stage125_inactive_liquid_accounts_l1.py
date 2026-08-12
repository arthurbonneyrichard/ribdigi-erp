"""Stage 125 L1 — inactive liquid cash/bank accounts honesty."""

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
async def test_liquid_accounts_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={"kind": "cash", "code": "1099", "name": "Stage125 Temp Cash"},
    )
    assert created.status_code == 200, created.text
    aid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/accounting/liquid-accounts/{aid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["is_active"] is False

    inactive = await ac.get(
        "/api/v1/accounting/liquid-accounts?is_active=false", headers=headers
    )
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == aid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get(
        "/api/v1/accounting/liquid-accounts?is_active=true", headers=headers
    )
    assert active.status_code == 200, active.text
    assert not any(r["id"] == aid for r in active.json()["data"])

    reactivated = await ac.patch(
        f"/api/v1/accounting/liquid-accounts/{aid}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["data"]["is_active"] is True


def test_shell_and_accounting_inactive_liquid_l1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "liquid_active=false" in shell
    assert "Inactive Liquid Accounts" in shell
    assert "Active Liquid Accounts" in shell
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 125" in page
    assert "liquidActiveFilter" in page
    assert "liquid_active" in page
