"""Stage 163 S1 — /sync/status honesty (deferred, empty)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_sync_status_deferred_honesty_s1(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    res = await ac.get("/api/v1/sync/status", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["sync_enabled"] is False
    assert data["queue_depth"] == 0
    assert data["pending_pushes"] == 0
    assert data["pending_pulls"] == 0
    assert data["last_sync_at"] is None
    assert data["conflict_count"] == 0
    assert "deferred" in (data.get("message") or "").lower() or "Stage 164" in (
        data.get("message") or ""
    )
    assert "fake" in (data.get("message") or "").lower()


@pytest.mark.asyncio
async def test_sync_status_requires_auth_s1(client):
    ac, _seed = client
    res = await ac.get("/api/v1/sync/status")
    assert res.status_code in {401, 403}, res.text


def test_sync_push_pull_not_claimed_complete_s1():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert '/sync/status' in api or '"/sync/status"' in api
    # Stage 163 must not ship fake push/pull success handlers as Complete.
    assert "@api.post(\"/sync/push\")" not in api
    assert "@api.post(\"/sync/pull\")" not in api
