"""Stage 128 S1 — session status honesty + secret-free CSV."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_sessions_status_filter_and_export(client):
    ac, seed = client

    login_a = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login_a.status_code == 200, login_a.text
    refresh_a = login_a.json()["data"]["refresh_token"]

    login_b = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "mgr@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login_b.status_code == 200, login_b.text
    headers = {
        "Authorization": f"Bearer {login_b.json()['data']['access_token']}",
        "X-Tenant-ID": seed["t1"].id,
    }

    active = await ac.get("/api/v1/auth/sessions?status=active", headers=headers)
    assert active.status_code == 200, active.text
    items = active.json()["data"]
    assert len(items) >= 2
    assert all(r.get("status") == "active" for r in items)
    assert any(r.get("current") for r in items)

    other = next(s for s in items if not s.get("current"))
    revoked = await ac.delete(f"/api/v1/auth/sessions/{other['id']}", headers=headers)
    assert revoked.status_code == 200, revoked.text

    only_revoked = await ac.get("/api/v1/auth/sessions?status=revoked", headers=headers)
    assert only_revoked.status_code == 200, only_revoked.text
    rows = only_revoked.json()["data"]
    assert any(r["id"] == other["id"] for r in rows)
    assert all(r.get("status") == "revoked" for r in rows)

    active_after = await ac.get("/api/v1/auth/sessions?status=active", headers=headers)
    assert not any(r["id"] == other["id"] for r in active_after.json()["data"])

    all_rows = await ac.get("/api/v1/auth/sessions?status=all", headers=headers)
    assert all_rows.status_code == 200, all_rows.text
    assert any(r["id"] == other["id"] for r in all_rows.json()["data"])

    exported = await ac.get("/api/v1/auth/sessions/export?status=revoked", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "status" in header and "ip_address" in header
    lower = header.lower()
    assert "refresh" not in lower and "token_hash" not in lower and "secret" not in lower
    assert "revoked" in exported.text

    # Old refresh from revoked session must fail
    reuse = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_a})
    assert reuse.status_code == 401


def test_shell_and_security_session_status_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "session_status=active" in shell
    assert "session_status=revoked" in shell
    assert "Revoked Sessions" in shell
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 128" in page
    assert "sessionStatusFilter" in page
    assert "/auth/sessions/export" in page
