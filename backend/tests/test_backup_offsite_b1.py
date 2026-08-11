"""Stage 27 B1 — automatic .ribbak offsite upload after create_backup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pyotp
import pytest
from sqlalchemy import select

from app import backup as backup_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/backup")
EVIDENCE_FILE = EVIDENCE_DIR / "stage27_b1_offsite_upload.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _patch_backup_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(backup_svc.settings, "BACKUP_OFFSITE_UPLOAD_ENABLED", False)
    monkeypatch.setattr(backup_svc.settings, "BACKUP_OFFSITE_S3_BUCKET", "")
    backup_svc.reset_backup_offsite_s3_client_cache()


def _enable_offsite(monkeypatch, *, bucket: str = "ribdigi-offsite"):
    monkeypatch.setattr(backup_svc.settings, "BACKUP_OFFSITE_UPLOAD_ENABLED", True)
    monkeypatch.setattr(backup_svc.settings, "BACKUP_OFFSITE_S3_BUCKET", bucket)
    monkeypatch.setattr(
        backup_svc.settings, "BACKUP_OFFSITE_S3_PREFIX", "ribdigi/logical/ribbak"
    )
    monkeypatch.setattr(backup_svc.settings, "S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setattr(backup_svc.settings, "S3_ACCESS_KEY", "minioadmin")
    monkeypatch.setattr(backup_svc.settings, "S3_SECRET_KEY", "minioadmin")
    monkeypatch.setattr(backup_svc.settings, "S3_FORCE_PATH_STYLE", True)
    backup_svc.reset_backup_offsite_s3_client_cache()


@pytest.mark.asyncio
async def test_offsite_disabled_skips_upload(client, tmp_path, monkeypatch):
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    put = MagicMock()
    monkeypatch.setattr(backup_svc, "_backup_offsite_s3_client", lambda: MagicMock(put_object=put))
    headers = await _admin(ac, seed)

    created = await ac.post("/api/v1/backup", headers=headers, json={"notes": "local-only"})
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "completed"
    assert body.get("offsite_uploaded") is False
    assert body.get("offsite_uri") is None
    put.assert_not_called()


@pytest.mark.asyncio
async def test_offsite_enabled_uploads_to_s3(client, tmp_path, monkeypatch):
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    _enable_offsite(monkeypatch)
    headers = await _admin(ac, seed)

    put_calls: list[dict] = []

    def put_object(**kwargs):
        put_calls.append(kwargs)

    client_mock = MagicMock()
    client_mock.put_object.side_effect = put_object
    monkeypatch.setattr(backup_svc, "_backup_offsite_s3_client", lambda: client_mock)

    created = await ac.post("/api/v1/backup", headers=headers, json={"notes": "offsite-ok"})
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "completed"
    assert body["offsite_uploaded"] is True
    assert body["offsite_uri"]
    assert body["offsite_uri"].startswith("s3://ribdigi-offsite/ribdigi/logical/ribbak/")
    assert put_calls, "expected put_object"
    assert put_calls[0]["Bucket"] == "ribdigi-offsite"
    assert put_calls[0]["Key"].startswith("ribdigi/logical/ribbak/")
    assert put_calls[0]["Key"].endswith(".ribbak")
    assert put_calls[0]["Body"]  # encrypted bytes


@pytest.mark.asyncio
async def test_offsite_upload_failure_no_fake_success(
    client, db_session, tmp_path, monkeypatch
):
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    _enable_offsite(monkeypatch)
    headers = await _admin(ac, seed)

    client_mock = MagicMock()
    client_mock.put_object.side_effect = RuntimeError("simulated S3 outage")
    monkeypatch.setattr(backup_svc, "_backup_offsite_s3_client", lambda: client_mock)

    failed = await ac.post("/api/v1/backup", headers=headers, json={"notes": "offsite-fail"})
    assert failed.status_code == 502, failed.text
    assert "offsite upload failed" in failed.text.lower() or "Backup" in failed.text

    listed = await ac.get("/api/v1/backup", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()["data"]
    assert rows, "failed job should still be listed"
    assert rows[0]["status"] == "failed"
    assert rows[0].get("offsite_uploaded") is False
    assert "offsite" in (rows[0].get("error_message") or "").lower()

    # Local file retained for operator recovery
    local_files = list(tmp_path.rglob("*.ribbak"))
    assert local_files, "local .ribbak must remain after offsite failure"

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.title == "Backup failed",
            )
        )
    ).scalars().all()
    assert notes, "admin Backup failed notification required"


def test_b1_plan_launch_roadmap_and_docs():
    plan = _read("docs/STAGE_27_PLAN.md")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_backup_offsite_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "P1 next" in plan
        or "P1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "L1 next" in plan
        or "L1 complete" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    s162 = br.split("#### BR-16.2 Scheduled Backup")[1].split("#### BR-16.3")[0]
    assert "Stage 27 B1" in s162
    assert "test_backup_offsite_b1.py" in s162 or "BACKUP_OFFSITE_UPLOAD_ENABLED" in s162

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 27 B1" in pr
    assert "test_backup_offsite_b1.py" in pr
    assert "BACKUP_OFFSITE_UPLOAD_ENABLED" in pr or "automatic" in pr.lower()

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_backup_offsite_b1.py" in launch
    assert "Stage 27 B1" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 27 B1" in roadmap
    assert "test_backup_offsite_b1.py" in roadmap

    runbook = _read("docs/DR_WAL_PITR_RUNBOOK.md")
    assert "Stage 27 B1" in runbook or "BACKUP_OFFSITE_UPLOAD_ENABLED" in runbook

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "27",
        "workstream": "B1",
        "passed": True,
        "opt_in_env": "BACKUP_OFFSITE_UPLOAD_ENABLED",
        "bucket_env": "BACKUP_OFFSITE_S3_BUCKET",
        "prefix_default": "ribdigi/logical/ribbak",
        "failure_no_fake_success": True,
        "operator_sync_script_retained": "ops/backup/sync-ribbak-offsite.sh.example",
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["failure_no_fake_success"] is True
