"""Audit retention policy + cold archive (BR-17.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pyotp
from sqlalchemy import select

from app import audit as audit_svc
from app import models as m
from app import storage as storage_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_retention_policy_enforces_seven_years_minimum():
    policy = audit_svc.retention_policy()
    assert policy["retention_years"] >= 7
    assert policy["purge_allowed"] is False
    assert policy["cold_archive_after_days"] >= 1


@pytest.mark.asyncio
async def test_cold_archive_copies_aged_rows_and_marks_archived(
    client, db_session, tmp_path, monkeypatch
):
    ac, seed = client
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    tid = seed["t1"].id
    old = m.AuditLog(
        tenant_id=tid,
        user_id=seed["mgr1"].id,
        module="sales",
        action="legacy_sale",
        entity="invoice",
        entity_id="inv-old",
        details={"n": 1},
        prev_hash=audit_svc.GENESIS_HASH,
        integrity_hash="a" * 64,
        created_at=datetime.utcnow() - timedelta(days=400),
    )
    recent = m.AuditLog(
        tenant_id=tid,
        user_id=seed["mgr1"].id,
        module="sales",
        action="recent_sale",
        entity="invoice",
        entity_id="inv-new",
        details={"n": 2},
        prev_hash="a" * 64,
        integrity_hash="b" * 64,
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add_all([old, recent])
    await db_session.commit()

    headers = await _super(ac, seed)
    policy = await ac.get("/api/v1/audit-logs/retention", headers=headers)
    assert policy.status_code == 200, policy.text
    assert policy.json()["data"]["retention_years"] >= 7
    assert policy.json()["data"]["purge_allowed"] is False

    archived = await ac.post(
        "/api/v1/audit-logs/archive-cold?older_than_days=30",
        headers=headers,
    )
    assert archived.status_code == 200, archived.text
    body = archived.json()["data"]
    assert body["archived"] >= 1
    assert body["storage_key"]
    assert body["sha256"]
    key_path = Path(tmp_path) / body["storage_key"]
    assert key_path.is_file()
    text = key_path.read_text(encoding="utf-8")
    assert "legacy_sale" in text
    assert "recent_sale" not in text

    await db_session.refresh(old)
    await db_session.refresh(recent)
    assert old.archived_at is not None
    assert recent.archived_at is None

    listed = await ac.get("/api/v1/audit-logs/archives", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(a["id"] == body["archive_id"] for a in listed.json()["data"])

    again = await ac.post(
        "/api/v1/audit-logs/archive-cold?older_than_days=30",
        headers=headers,
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["archived"] == 0

    blocked = await ac.delete(f"/api/v1/audit-logs/{old.id}", headers=headers)
    assert blocked.status_code == 405


@pytest.mark.asyncio
async def test_archive_cold_job_registered():
    from app import jobs as jobs_svc

    assert "archive_cold_audit_logs" in jobs_svc.JOB_HANDLERS


def test_audit_cold_archive_ui_packaged():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    page = (root / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "/audit-logs/retention" in page
    assert "/audit-logs/archives" in page
    assert "/audit-logs/archive-cold" in page
    assert "Archive cold now" in page
    assert "from_date" in page
    assert "archived_at" in page
    readiness = (root / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "Audit cold-archive UI" in readiness or "cold-archive UI" in readiness
