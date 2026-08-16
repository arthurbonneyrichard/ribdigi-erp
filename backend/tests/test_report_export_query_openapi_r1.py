"""GET /reports/export report_type + format Query OpenAPI Literals (BR-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.report_export import EXPORTABLE, EXPORT_FORMATS
from app.schemas import ReportExportFormatValue, ReportTypeValue

ROOT = Path(__file__).resolve().parents[2]


def test_report_export_query_literals_cover_catalog():
    lit = ReportTypeValue.__args__[0]
    assert set(lit.__args__) == set(EXPORTABLE)
    fmt = ReportExportFormatValue.__args__[0]
    assert set(fmt.__args__) == set(EXPORT_FORMATS)


def test_report_export_query_literal_schema():
    rt = TypeAdapter(ReportTypeValue)
    assert rt.validate_python("  Profit_Loss ") == "profit_loss"
    with pytest.raises(ValidationError):
        rt.validate_python("")
    with pytest.raises(ValidationError):
        rt.validate_python("not_a_report")

    fmt = TypeAdapter(ReportExportFormatValue)
    assert fmt.validate_python("XLSX") == "xlsx"
    with pytest.raises(ValidationError):
        fmt.validate_python("")
    with pytest.raises(ValidationError):
        fmt.validate_python("docx")


def test_report_export_query_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "/reports/export" in page
    assert "download('csv'" in page or 'download("csv"' in page
    assert "download('xlsx'" in page or 'download("xlsx"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report export query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "One-shot export" in docs
