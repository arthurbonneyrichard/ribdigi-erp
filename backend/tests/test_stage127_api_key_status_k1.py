"""Stage 127 K1 — API-key status honesty + secret-free CSV."""

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
async def test_api_keys_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Stage127 Soon Revoked"},
    )
    assert created.status_code == 200, created.text
    kid = created.json()["data"]["id"]
    assert "api_key" in created.json()["data"]

    active = await ac.get("/api/v1/api-keys?status=active", headers=headers)
    assert active.status_code == 200, active.text
    assert any(r["id"] == kid for r in active.json()["data"])
    assert all(r.get("status") == "active" for r in active.json()["data"])

    revoked = await ac.delete(f"/api/v1/api-keys/{kid}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["status"] == "revoked"

    only_revoked = await ac.get("/api/v1/api-keys?status=revoked", headers=headers)
    assert only_revoked.status_code == 200, only_revoked.text
    rows = only_revoked.json()["data"]
    assert any(r["id"] == kid for r in rows)
    assert all(r.get("status") == "revoked" for r in rows)

    active_after = await ac.get("/api/v1/api-keys?status=active", headers=headers)
    assert not any(r["id"] == kid for r in active_after.json()["data"])

    exported = await ac.get("/api/v1/api-keys/export?status=revoked", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "key_prefix" in header and "status" in header
    assert "secret" not in header.lower() and "key_hash" not in header.lower()
    assert "api_key" not in header.lower() or header.lower().count("api_key") == 0
    assert "Stage127 Soon Revoked" in exported.text or "revoked" in exported.text


def test_shell_and_security_api_key_status_k1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "api_key_status=active" in shell
    assert "api_key_status=revoked" in shell
    assert "Active API Keys" in shell
    assert "Revoked API Keys" in shell
    assert "Expired API Keys" in shell
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 127" in page
    assert "apiKeyStatusFilter" in page
    assert "/api-keys/export" in page
