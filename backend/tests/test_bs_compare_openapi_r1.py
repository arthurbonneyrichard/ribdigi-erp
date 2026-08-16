"""Balance sheet compare Query OpenAPI Literal (BR-14.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BalanceSheetCompareValue

ROOT = Path(__file__).resolve().parents[2]


def test_balance_sheet_compare_literal_schema():
    adapter = TypeAdapter(BalanceSheetCompareValue)
    assert adapter.validate_python("prior_period") == "prior_period"
    assert adapter.validate_python("  Prior_Year ") == "prior_year"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("prior_quarter")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_balance_sheet_compare_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'value="prior_period"' in page
    assert 'value="prior_year"' in page
    assert "No compare" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Balance sheet compare OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "compare" in docs and "prior_period" in docs
    assert "422" in docs
