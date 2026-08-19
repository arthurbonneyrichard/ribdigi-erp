"""Stage 164 Q1 — sync queue schema + real /sync/status counts."""

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
async def test_sync_status_enabled_with_real_counts_q1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    res = await ac.get("/api/v1/sync/status", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["sync_enabled"] is True
    assert data["queue_depth"] == 0
    assert data["pending_pushes"] == 0
    assert data["pending_pulls"] == 0
    assert data["conflict_count"] == 0
    assert "Stage 164" in (data.get("message") or "")


def test_sync_queue_models_and_migration_q1():
    models = (ROOT / "backend/app/models.py").read_text(encoding="utf-8")
    assert "class SyncQueueItem" in models
    assert "class SyncConflict" in models
    assert "client_request_id" in models
    mig = (
        ROOT / "backend/alembic/versions/20260813_0092_sync_queue_and_pos_idempotency.py"
    ).read_text(encoding="utf-8")
    assert "20260813_0092" in mig
    assert "sync_queue_items" in mig
    assert "sync_conflicts" in mig
    assert "client_request_id" in mig
