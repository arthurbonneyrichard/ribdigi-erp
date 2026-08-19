"""Stage 163 S1 — /sync/status honesty.

Stage 164 Q1 supersedes deferred-only status: sync_enabled may be true with real counts.
This file keeps Stage 163 honesty (no fabricated offline sales Completes).
"""

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
    assert "sync_enabled" in data
    assert data["queue_depth"] >= 0
    assert data["pending_pushes"] >= 0
    assert data["pending_pulls"] >= 0
    assert data["conflict_count"] >= 0
    message = data.get("message") or ""
    # Stage 163: deferred empty. Stage 164+: enabled queue with honest message.
    if data["sync_enabled"] is False:
        assert "deferred" in message.lower() or "fake" in message.lower()
    else:
        assert "Stage 164" in message or "queue" in message.lower()
        assert "Complete" not in message or "deferred" in message.lower()


@pytest.mark.asyncio
async def test_sync_status_requires_auth_s1(client):
    ac, _seed = client
    res = await ac.get("/api/v1/sync/status")
    assert res.status_code in {401, 403}, res.text


def test_sync_push_pull_stage163_supersession_note_s1():
    """Stage 163 historically forbade push/pull; Stage 164 ships real APIs."""
    fidelity = (ROOT / "docs/STAGE_163_FIDELITY.md").read_text(encoding="utf-8")
    assert "Stage 164" in fidelity or "deferred" in fidelity.lower()
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    # After Stage 164, push exists — honesty is "no fake Complete", not absence.
    assert "/sync/status" in api
