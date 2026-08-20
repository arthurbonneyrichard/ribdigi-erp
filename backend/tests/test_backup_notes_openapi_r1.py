"""BackupCreateBody.notes OpenAPI honesty (BR-16)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BackupCreateBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_backup_notes_schema():
    omit = BackupCreateBody.model_validate({})
    assert omit.notes is None
    ok = BackupCreateBody.model_validate({"notes": "  Manual pre-upgrade  "})
    assert ok.notes == "Manual pre-upgrade"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BackupCreateBody.model_validate({"notes": bad})
    with pytest.raises(ValidationError):
        BackupCreateBody.model_validate({"notes": "ok", "extra": 1})


def test_backup_notes_ui_and_docs():
    page = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Backup notes"' in page
    assert "backupNotes.trim() || null" in page
    assert 'aria-label="Create backup now"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "BackupNotesValue" in agents
    assert "BackupCreateBody" in agents
    docs = (ROOT / "docs/DR_LOGICAL_BACKUP_RUNBOOK.md").read_text(encoding="utf-8")
    assert "BackupNotesValue" in docs
    assert "Backup notes" in docs


@pytest.mark.asyncio
async def test_backup_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    tag = f"TIP184 notes {suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post("/api/v1/backup", headers=headers, json={"notes": bad})
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post("/api/v1/backup", headers=headers, json={})
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post("/api/v1/backup", headers=headers, json={"notes": f"  {tag}  "})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
