"""Scheduled backup failure alerts (BR-16.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import backup as backup_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_scheduled_backup_dir_not_writable_notifies(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    # Enable schedule and force due
    cfg = await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"enabled": True, "frequency": "daily", "retention_count": 5, "hour_utc": 0},
    )
    assert cfg.status_code == 200, cfg.text
    row = (
        await db_session.execute(
            select(m.BackupSettings).where(m.BackupSettings.tenant_id == tenant_id)
        )
    ).scalar_one()
    row.last_run_at = datetime.utcnow() - timedelta(days=2)
    await db_session.commit()

    bad = tmp_path / "readonly-backups"
    bad.mkdir()
    bad.chmod(0o500)
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(bad / "nested-missing"))
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(bad / "nested-missing"))

    # Parent is not writable → ensure_backup_dir_writable fails
    result = await backup_svc.run_scheduled_backup_if_due(
        db_session, tenant_id=tenant_id, user_id=seed["admin1"].id
    )
    await db_session.commit()

    assert result["ran"] is False
    assert result["reason"] == "dir_not_writable"

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.title == "Backup failed",
            )
        )
    ).scalars().all()
    assert notes, "expected Backup failed notification"
    assert any("dir_not_writable" in (n.message or "") for n in notes)

    listed = await ac.get(
        "/api/v1/notifications?status=unread&category=system",
        headers=headers,
    )
    assert listed.status_code == 200
    titles = {r.get("title") for r in listed.json()["data"] or []}
    assert "Backup failed" in titles


@pytest.mark.asyncio
async def test_scheduled_backup_create_failure_notifies(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")

    cfg = await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={"enabled": True, "frequency": "daily", "retention_count": 3, "hour_utc": 0},
    )
    assert cfg.status_code == 200, cfg.text
    row = (
        await db_session.execute(
            select(m.BackupSettings).where(m.BackupSettings.tenant_id == tenant_id)
        )
    ).scalar_one()
    row.last_run_at = datetime.utcnow() - timedelta(days=2)
    await db_session.commit()

    async def boom(*_a, **_k):
        raise RuntimeError("simulated collect failure")

    monkeypatch.setattr("app.backup.collect_tenant_payload", boom)

    result = await backup_svc.run_scheduled_backup_if_due(
        db_session, tenant_id=tenant_id, user_id=seed["admin1"].id
    )
    await db_session.commit()

    assert result["ran"] is False
    assert result["reason"] == "failed"

    jobs = (
        await db_session.execute(
            select(m.BackupJob).where(
                m.BackupJob.tenant_id == tenant_id,
                m.BackupJob.status == "failed",
            )
        )
    ).scalars().all()
    assert jobs

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.title == "Backup failed",
            )
        )
    ).scalars().all()
    assert any("simulated collect failure" in (n.message or "") for n in notes)
