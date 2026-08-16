"""BankAutoClearBody.min_confidence OpenAPI Literal (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import BankAutoClearBody

ROOT = Path(__file__).resolve().parents[2]


def test_bank_auto_clear_confidence_literal_schema():
    bare = BankAutoClearBody.model_validate({})
    assert bare.min_confidence == "high"
    assert bare.date_window_days == 7

    ok = BankAutoClearBody.model_validate(
        {"min_confidence": "  Medium ", "date_window_days": 14}
    )
    assert ok.min_confidence == "medium"
    assert ok.date_window_days == 14

    low = BankAutoClearBody.model_validate({"min_confidence": "LOW"})
    assert low.min_confidence == "low"

    with pytest.raises(ValidationError):
        BankAutoClearBody.model_validate({"min_confidence": ""})
    with pytest.raises(ValidationError):
        BankAutoClearBody.model_validate({"min_confidence": "   "})
    with pytest.raises(ValidationError):
        BankAutoClearBody.model_validate({"min_confidence": "ultra"})
    with pytest.raises(ValidationError):
        BankAutoClearBody.model_validate({"date_window_days": 0})


def test_bank_auto_clear_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "autoClear('high')" in page
    assert "autoClear('medium')" in page
    assert "autoClear('low')" in page
    assert "Auto-clear" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank recon auto-clear confidence OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "auto-clear" in docs
    assert "min_confidence" in docs
