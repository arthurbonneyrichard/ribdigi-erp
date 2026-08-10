"""Stage 18 B1: backup schedule, retention prune, failure notify, restore drill green."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import func, select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _patch_backup_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))


@pytest.mark.asyncio
async def test_backup_settings_schedule_daily_weekly(client, tmp_path, monkeypatch):
    """BR-16.2: configurable schedule (daily, weekly) via settings API."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    got = await ac.get("/api/v1/backup/settings", headers=headers)
    assert got.status_code == 200, got.text
    assert "enabled" in got.json()["data"]
    assert got.json()["data"]["frequency"] in {"daily", "weekly"}

    daily = await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"enabled": True, "frequency": "daily", "retention_count": 5, "hour_utc": 0},
    )
    assert daily.status_code == 200, daily.text
    body = daily.json()["data"]
    assert body["enabled"] is True
    assert body["frequency"] == "daily"
    assert body["retention_count"] == 5
    assert body["hour_utc"] == 0

    weekly = await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"frequency": "weekly"},
    )
    assert weekly.status_code == 200, weekly.text
    assert weekly.json()["data"]["frequency"] == "weekly"

    bad = await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"frequency": "hourly"},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_scheduled_run_due_and_skip_reasons(client, db_session, tmp_path, monkeypatch):
    """Schedule run-due creates when due; skips when disabled or already ran."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    disabled = await ac.post("/api/v1/backup/run-due", headers=headers)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["data"]["ran"] is False
    assert disabled.json()["data"]["reason"] == "schedule_disabled"

    await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"enabled": True, "frequency": "daily", "hour_utc": 0, "retention_count": 10},
    )

    created = await ac.post("/api/v1/backup/run-due", headers=headers)
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["ran"] is True
    assert data["reason"] == "created"
    assert data["backup_id"]
    assert data.get("filename")

    again = await ac.post("/api/v1/backup/run-due", headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["ran"] is False
    assert again.json()["data"]["reason"] == "already_ran"

    listed = await ac.get("/api/v1/backup", headers=headers)
    assert listed.status_code == 200
    jobs = listed.json()["data"]
    assert any(j["id"] == data["backup_id"] and j["status"] == "completed" for j in jobs)
    assert any(j.get("notes") == "scheduled" for j in jobs)


@pytest.mark.asyncio
async def test_retention_prune_keeps_last_n(client, db_session, tmp_path, monkeypatch):
    """BR-16.2: retention policy keeps last N completed backups."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"retention_count": 2},
    )

    ids = []
    for i in range(3):
        r = await ac.post("/api/v1/backup", headers=headers, json={"notes": f"retain-{i}"})
        assert r.status_code == 200, r.text
        ids.append(r.json()["data"]["id"])

    listed = await ac.get("/api/v1/backup", headers=headers)
    assert listed.status_code == 200
    remaining = [j for j in listed.json()["data"] if j["status"] == "completed"]
    assert len(remaining) == 2
    remaining_ids = {j["id"] for j in remaining}
    assert ids[0] not in remaining_ids
    assert ids[1] in remaining_ids
    assert ids[2] in remaining_ids

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(m.BackupJob)
            .where(
                m.BackupJob.tenant_id == seed["t1"].id,
                m.BackupJob.status == "completed",
            )
        )
    ).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_backup_failure_notifies_admin_no_fake_success(
    client, db_session, tmp_path, monkeypatch
):
    """BR-16.2: failure alerts admin; job marked failed (no fake success)."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    def _boom(*_a, **_k):
        raise RuntimeError("simulated encrypt failure")

    monkeypatch.setattr("app.backup.encrypt_payload", _boom)

    failed = await ac.post("/api/v1/backup", headers=headers, json={"notes": "expect-fail"})
    assert failed.status_code == 500
    assert "Backup failed" in failed.text
    assert "success" not in failed.json().get("message", "").lower()

    job = (
        await db_session.execute(
            select(m.BackupJob)
            .where(m.BackupJob.tenant_id == seed["t1"].id, m.BackupJob.status == "failed")
            .order_by(m.BackupJob.created_at.desc())
        )
    ).scalars().first()
    assert job is not None
    assert job.error_message
    assert "encrypt" in job.error_message.lower() or "simulated" in job.error_message.lower()

    note = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.title == "Backup failed",
                m.Notification.entity_id == job.id,
            )
        )
    ).scalar_one_or_none()
    assert note is not None
    assert note.category == "system"
    assert note.status == "unread"

    listed = await ac.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200
    titles = [n["title"] for n in listed.json()["data"]]
    assert "Backup failed" in titles


@pytest.mark.asyncio
async def test_scheduled_failure_returns_failed_reason_and_notifies(
    client, db_session, tmp_path, monkeypatch
):
    """Scheduled run-due must not pretend success when create fails."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"enabled": True, "frequency": "daily", "hour_utc": 0},
    )

    # Clear last_run so schedule is due
    settings_row = (
        await db_session.execute(
            select(m.BackupSettings).where(m.BackupSettings.tenant_id == seed["t1"].id)
        )
    ).scalar_one()
    settings_row.last_run_at = None
    await db_session.commit()

    monkeypatch.setattr(
        "app.backup.encrypt_payload",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("scheduled boom")),
    )

    result = await ac.post("/api/v1/backup/run-due", headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()["data"]
    assert body["ran"] is False
    assert body["reason"] == "failed"

    note = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.title == "Backup failed",
            )
        )
    ).scalars().first()
    assert note is not None


@pytest.mark.asyncio
async def test_restore_dry_run_and_verify_still_green(client, tmp_path, monkeypatch):
    """B1 AC: restore dry-run / verify path remains green alongside schedule work."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    created = await ac.post("/api/v1/backup", headers=headers, json={"notes": "b1-green"})
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]

    dry = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": True},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["data"]["valid"] is True
    assert dry.json()["data"]["dry_run"] is True

    verify = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=headers,
        json={"sample_limit": 20},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["proof"]["ok"] is True


@pytest.mark.asyncio
async def test_weekly_gap_skips_until_due(client, db_session, tmp_path, monkeypatch):
    """Weekly frequency enforces 7-day gap after last_run_at."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)

    await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"enabled": True, "frequency": "weekly", "hour_utc": 0},
    )
    settings_row = (
        await db_session.execute(
            select(m.BackupSettings).where(m.BackupSettings.tenant_id == seed["t1"].id)
        )
    ).scalar_one()
    settings_row.last_run_at = datetime.utcnow() - timedelta(days=3)
    await db_session.commit()

    skip = await ac.post("/api/v1/backup/run-due", headers=headers)
    assert skip.status_code == 200
    assert skip.json()["data"]["ran"] is False
    assert skip.json()["data"]["reason"] == "already_ran"

    settings_row.last_run_at = datetime.utcnow() - timedelta(days=8)
    await db_session.commit()

    due = await ac.post("/api/v1/backup/run-due", headers=headers)
    assert due.status_code == 200, due.text
    assert due.json()["data"]["ran"] is True
    assert due.json()["data"]["reason"] == "created"
