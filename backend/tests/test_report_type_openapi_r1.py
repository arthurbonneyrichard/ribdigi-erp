"""Report schedule report_type OpenAPI Literal (BR-14 / EXPORTABLE)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.report_export import EXPORTABLE
from app.schemas import ReportScheduleCreate, ReportScheduleUpdate, ReportTypeValue

ROOT = Path(__file__).resolve().parents[2]


def test_report_type_literal_covers_exportable():
    # Annotated[Literal[...], BeforeValidator] → args[0] is the Literal
    lit = ReportTypeValue.__args__[0]
    values = set(lit.__args__)
    assert values == set(EXPORTABLE)


def test_report_schedule_report_type_literal_schema():
    ok = ReportScheduleCreate.model_validate(
        {
            "name": "P&L weekly",
            "report_type": "  Profit_Loss ",
            "frequency": "weekly",
            "weekday": 1,
            "recipients": "ops@example.com",
        }
    )
    assert ok.report_type == "profit_loss"

    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Bad",
                "report_type": "not_a_report",
                "recipients": "a@example.com",
            }
        )
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Bad",
                "report_type": "",
                "recipients": "a@example.com",
            }
        )
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Bad",
                "recipients": "a@example.com",
            }
        )

    patch = ReportScheduleUpdate.model_validate({"report_type": "Inventory_Movements"})
    assert patch.report_type == "inventory_movements"
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"report_type": "garbage_xyz"})
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"report_type": "  "})


def test_report_schedule_report_type_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "REPORT_TYPES" in page
    for key in (
        "profit_loss",
        "inventory_movements",
        "purchases_suppliers",
        "summary",
        "tax_filing_gh",
    ):
        assert f"'{key}'" in page or f'"{key}"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "report_type" in agents and "EXPORTABLE" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Email report schedules" in docs
    assert "report_type" in docs and "EXPORTABLE" in docs
