"""Stage 121 S1 — inactive stores honesty (?is_active=false)."""

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
async def test_stores_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "INA121", "name": "Soon Inactive Store"},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/stores?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == sid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/stores?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert all(r.get("is_active") is not False for r in active.json()["data"])
    assert not any(r["id"] == sid for r in active.json()["data"])

    active_only = await ac.get("/api/v1/stores?active_only=true", headers=headers)
    assert active_only.status_code == 200, active_only.text
    assert not any(r["id"] == sid for r in active_only.json()["data"])


def test_shell_and_stores_inactive_stores_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "store_active=false" in shell
    assert "Inactive Stores" in shell
    assert "Active Stores" in shell
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 121" in page
    assert "store_active" in page
    assert "storeActiveFilter" in page
