"""Report schedule frequency/format OpenAPI Literals (BR-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import ReportScheduleCreate, ReportScheduleUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_report_schedule_frequency_format_literal_schema():
    ok = ReportScheduleCreate.model_validate(
        {
            "name": "Weekly sales",
            "report_type": "profit_loss",
            "frequency": "weekly",
            "format": "CSV",
            "weekday": 1,
            "recipients": "ops@example.com",
        }
    )
    assert ok.frequency == "weekly"
    assert ok.format == "csv"

    defaulted = ReportScheduleCreate.model_validate(
        {
            "name": "Daily sales",
            "report_type": "profit_loss",
            "recipients": ["a@example.com"],
        }
    )
    assert defaulted.frequency == "daily"
    assert defaulted.format == "xlsx"

    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Bad",
                "report_type": "profit_loss",
                "frequency": "",
                "recipients": "a@example.com",
            }
        )
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Bad",
                "report_type": "profit_loss",
                "frequency": "monthly",
                "recipients": "a@example.com",
            }
        )
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Bad",
                "report_type": "profit_loss",
                "format": "docx",
                "recipients": "a@example.com",
            }
        )

    patch = ReportScheduleUpdate.model_validate({"frequency": "  Weekly "})
    assert patch.frequency == "weekly"
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"frequency": "garbage_xyz"})
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"format": ""})


def test_report_schedule_frequency_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "frequency" in page
    assert 'value="daily"' in page
    assert 'value="weekly"' in page
    assert 'value="xlsx"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report schedule frequency/format OpenAPI" in agents
