"""BackupSettingsUpdate.frequency OpenAPI Literal (BR-16)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import BackupSettingsUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_backup_frequency_literal_schema():
    ok = BackupSettingsUpdate.model_validate({"frequency": "weekly"})
    assert ok.frequency == "weekly"

    coerced = BackupSettingsUpdate.model_validate({"frequency": "  Daily "})
    assert coerced.frequency == "daily"

    omitted = BackupSettingsUpdate.model_validate({"enabled": True})
    assert omitted.frequency is None

    with pytest.raises(ValidationError):
        BackupSettingsUpdate.model_validate({"frequency": ""})
    with pytest.raises(ValidationError):
        BackupSettingsUpdate.model_validate({"frequency": "   "})
    with pytest.raises(ValidationError):
        BackupSettingsUpdate.model_validate({"frequency": "monthly"})
    with pytest.raises(ValidationError):
        BackupSettingsUpdate.model_validate({"frequency": "garbage_xyz"})

    # Bounds on companion fields (schema honesty)
    with pytest.raises(ValidationError):
        BackupSettingsUpdate.model_validate({"retention_count": 0})
    with pytest.raises(ValidationError):
        BackupSettingsUpdate.model_validate({"hour_utc": 24})


def test_backup_frequency_ui_and_docs():
    page = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert "frequency" in page
    assert 'value="daily"' in page
    assert 'value="weekly"' in page
    runbook = (ROOT / "docs/DR_LOGICAL_BACKUP_RUNBOOK.md").read_text(encoding="utf-8")
    assert 'Literal["daily","weekly"]' in runbook
    assert "422" in runbook
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Backup frequency OpenAPI" in agents
