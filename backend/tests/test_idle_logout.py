"""Server-side idle logout (Stage 1 A3)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_idle_logout_revokes_current_session(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    listed = await ac.get("/api/v1/auth/sessions", headers=headers)
    assert listed.status_code == 200, listed.text
    before = listed.json()["data"]
    assert len(before) >= 1
    current = next((s for s in before if s.get("current")), before[0])

    idle = await ac.post("/api/v1/auth/idle-logout", headers=headers, json={})
    assert idle.status_code == 200, idle.text
    assert idle.json()["data"]["revoked"] is True

    # Access token should no longer work once session jti is revoked
    after = await ac.get("/api/v1/auth/sessions", headers=headers)
    assert after.status_code == 401, after.text

    # Fresh login works
    again = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    ok = await ac.get("/api/v1/me", headers=again)
    assert ok.status_code == 200, ok.text
