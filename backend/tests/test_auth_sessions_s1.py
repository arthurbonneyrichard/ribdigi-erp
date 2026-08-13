"""Auth session list, revoke, and refresh rotation (BR-19.3)."""

from __future__ import annotations

import pyotp
import pytest


async def _login(ac, seed, *, email="super@alpha.example.com"):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    body = {
        "email": email,
        "password": "SecurePass123!",
        "tenant_id": "alpha",
        "totp_code": code,
    }
    r = await ac.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("access_token")
    assert data.get("refresh_token")
    return data


@pytest.mark.asyncio
async def test_list_and_revoke_own_sessions(client):
    ac, seed = client
    first = await _login(ac, seed)
    headers = {
        "Authorization": f"Bearer {first['access_token']}",
        "X-Tenant-ID": first["user"]["tenant_id"],
    }

    # Second login creates another active session for the same user.
    second = await _login(ac, seed)

    listed = await ac.get("/api/v1/auth/sessions", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert len(rows) >= 2
    assert sum(1 for r in rows if r.get("current")) == 1
    other = next(r for r in rows if not r.get("current"))

    revoked = await ac.delete(f"/api/v1/auth/sessions/{other['id']}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["revoked"] is True

    # Revoked session's refresh must fail.
    bad_refresh = await ac.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert bad_refresh.status_code == 401

    after = await ac.get("/api/v1/auth/sessions", headers=headers)
    assert after.status_code == 200
    ids = {r["id"] for r in after.json()["data"]}
    assert other["id"] not in ids

    missing = await ac.delete("/api/v1/auth/sessions/nonexistent", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_refresh_token_rotation(client):
    ac, seed = client
    login = await _login(ac, seed)
    old_refresh = login["refresh_token"]

    rotated = await ac.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200, rotated.text
    data = rotated.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != old_refresh

    reuse = await ac.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401

    again = await ac.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert again.status_code == 200, again.text
