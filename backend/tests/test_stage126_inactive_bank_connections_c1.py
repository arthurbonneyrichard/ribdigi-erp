"""Stage 126 C1 — inactive bank connections honesty."""

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
async def test_bank_connections_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()["data"]
    bank = next((a for a in accounts if a.get("code") == "1010"), accounts[0])

    created = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "mock",
            "display_name": "Stage126 Soon Inactive",
            "external_account_id": "stage126-inactive-1",
        },
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["is_active"] is False

    inactive = await ac.get(
        "/api/v1/accounting/bank-connections?is_active=false", headers=headers
    )
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == cid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get(
        "/api/v1/accounting/bank-connections?is_active=true", headers=headers
    )
    assert active.status_code == 200, active.text
    assert not any(r["id"] == cid for r in active.json()["data"])

    reactivated = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["data"]["is_active"] is True


def test_shell_and_accounting_inactive_bank_connections_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "bank_conn_active=false" in shell
    assert "Inactive Bank Connections" in shell
    assert "Active Bank Connections" in shell
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 126" in page
    assert "bankConnActiveFilter" in page
    assert "bank_conn_active" in page
