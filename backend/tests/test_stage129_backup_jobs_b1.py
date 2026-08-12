"""Stage 129 B1 — backup job status filter + metadata CSV."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_backup_jobs_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    db_session.add_all(
        [
            m.BackupJob(
                tenant_id=seed["t1"].id,
                status="completed",
                filename="ok.ribbak",
                storage_path="/tmp/ok.ribbak",
                size_bytes=10,
                checksum_sha256="abc123",
                encrypted=False,
                notes="Stage129 completed",
            ),
            m.BackupJob(
                tenant_id=seed["t1"].id,
                status="failed",
                filename="bad.ribbak",
                storage_path="/tmp/bad.ribbak",
                size_bytes=0,
                checksum_sha256="",
                encrypted=False,
                notes="Stage129 failed",
                error_message="boom",
            ),
        ]
    )
    await db_session.commit()

    completed = await ac.get("/api/v1/backup?status=completed", headers=headers)
    assert completed.status_code == 200, completed.text
    rows = completed.json()["data"]
    assert any(r.get("notes") == "Stage129 completed" for r in rows)
    assert all(r.get("status") == "completed" for r in rows)

    failed = await ac.get("/api/v1/backup?status=failed", headers=headers)
    assert failed.status_code == 200, failed.text
    frows = failed.json()["data"]
    assert any(r.get("notes") == "Stage129 failed" for r in frows)
    assert all(r.get("status") == "failed" for r in frows)

    exported = await ac.get("/api/v1/backup/export?status=failed", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "status" in header and "filename" in header and "checksum_sha256" in header
    assert "storage_path" not in header.lower()
    assert "Stage129 failed" in exported.text or "failed" in exported.text
    assert "boom" in exported.text


def test_shell_and_backup_jobs_b1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "backup_status=completed" in shell
    assert "backup_status=failed" in shell
    assert "Completed Backups" in shell
    assert "Failed Backups" in shell
    page = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert "Stage 129" in page
    assert "backupStatusFilter" in page
    assert "/backup/export" in page
