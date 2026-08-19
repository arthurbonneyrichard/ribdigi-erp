"""Stage 129 A1 — tenant-wide admin session inventory + secret-free CSV."""

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
async def test_tenant_sessions_status_filter_and_export(client):
    ac, seed = client

    # Two manager logins create sessions under mgr
    for _ in range(2):
        login = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "mgr@alpha.example.com",
                "password": "SecurePass123!",
                "tenant_id": "alpha",
            },
        )
        assert login.status_code == 200, login.text

    headers = await _super(ac, seed)

    active = await ac.get("/api/v1/auth/tenant-sessions?status=active", headers=headers)
    assert active.status_code == 200, active.text
    rows = active.json()["data"]
    assert len(rows) >= 2
    assert all(r.get("status") == "active" for r in rows)
    assert any(r.get("user_email") == "mgr@alpha.example.com" for r in rows)
    assert any(r.get("user_email") == "super@alpha.example.com" for r in rows)

    # Revoke one manager session via manager's own API
    mgr_login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert mgr_login.status_code == 200, mgr_login.text
    mgr_headers = {
        "Authorization": f"Bearer {mgr_login.json()['data']['access_token']}",
        "X-Tenant-ID": seed["t1"].id,
    }
    mine = await ac.get("/api/v1/auth/sessions?status=active", headers=mgr_headers)
    other = next(s for s in mine.json()["data"] if not s.get("current"))
    revoked = await ac.delete(f"/api/v1/auth/sessions/{other['id']}", headers=mgr_headers)
    assert revoked.status_code == 200, revoked.text

    only_revoked = await ac.get(
        "/api/v1/auth/tenant-sessions?status=revoked", headers=headers
    )
    assert only_revoked.status_code == 200, only_revoked.text
    rev_rows = only_revoked.json()["data"]
    assert any(r["id"] == other["id"] for r in rev_rows)
    assert all(r.get("status") == "revoked" for r in rev_rows)

    exported = await ac.get(
        "/api/v1/auth/tenant-sessions/export?status=revoked", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "user_email" in header and "status" in header
    lower = header.lower()
    assert "refresh" not in lower and "token_hash" not in lower and "secret" not in lower
    assert "revoked" in exported.text

    # Non-admin cannot list tenant sessions
    denied = await ac.get("/api/v1/auth/tenant-sessions", headers=mgr_headers)
    assert denied.status_code in {401, 403}


def test_shell_and_security_tenant_sessions_a1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "tenant_session_status=active" in shell
    assert "tenant_session_status=revoked" in shell
    assert "Tenant Active Sessions" in shell
    assert "Tenant Revoked Sessions" in shell
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 129" in page
    assert "tenantSessionStatusFilter" in page
    assert "/auth/tenant-sessions/export" in page
