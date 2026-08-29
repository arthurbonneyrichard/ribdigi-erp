"""GET /backup status Query OpenAPI Literal + Backup manage filter (BR-16)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BackupJobStatusFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_backup_job_status_filter_literal_schema():
    adapter = TypeAdapter(BackupJobStatusFilterValue)
    assert adapter.validate_python("pending") == "pending"
    assert adapter.validate_python("  Completed ") == "completed"
    assert adapter.validate_python("FAILED") == "failed"
    assert adapter.validate_python("restoring") == "restoring"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("success")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_backup_job_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert "backupManageFilter" in page
    assert "managedBackups" in page
    assert 'aria-label="Backup job status filter"' in page
    assert 'value="completed"' in page
    assert 'value="failed"' in page
    assert 'value="restoring"' in page
    assert "No backups for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Backup job status Query OpenAPI" in agents
    assert "backupManageFilter" in agents
    docs = (ROOT / "docs/DR_LOGICAL_BACKUP_RUNBOOK.md").read_text(encoding="utf-8")
    assert "backupManageFilter" in docs
    assert "pending" in docs and "422" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_backup_job_status_filter_api_blank_invalid_422(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    blank = await ac.get("/api/v1/backup?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/backup?status=success", headers=headers)
    assert bad.status_code == 422, bad.text

    created = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "status filter probe"}
    )
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]
    status = created.json()["data"]["status"]
    assert status in {"pending", "completed", "failed", "restoring"}

    filtered = await ac.get(f"/api/v1/backup?status={status}", headers=headers)
    assert filtered.status_code == 200, filtered.text
    rows = filtered.json()["data"]
    assert any(r["id"] == backup_id for r in rows)
    assert all(r["status"] == status for r in rows)

    cased = await ac.get("/api/v1/backup?status=Completed", headers=headers)
    assert cased.status_code == 200, cased.text
    assert all(r["status"] == "completed" for r in cased.json()["data"])

    other = "failed" if status != "failed" else "pending"
    other_rows = await ac.get(f"/api/v1/backup?status={other}", headers=headers)
    assert other_rows.status_code == 200, other_rows.text
    assert all(r["status"] == other for r in other_rows.json()["data"])
    assert not any(r["id"] == backup_id for r in other_rows.json()["data"])

    omit = await ac.get("/api/v1/backup", headers=headers)
    assert omit.status_code == 200, omit.text
