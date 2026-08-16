"""Cash transfer kind OpenAPI Literal (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import CashTransferCreate

ROOT = Path(__file__).resolve().parents[2]


def test_cash_transfer_kind_literal_schema():
    ok = CashTransferCreate.model_validate({"kind": "deposit", "amount": 10})
    assert ok.kind == "deposit"
    defaulted = CashTransferCreate.model_validate({"amount": 10})
    assert defaulted.kind == "transfer"
    with pytest.raises(ValidationError):
        CashTransferCreate.model_validate({"amount": 10, "kind": ""})
    with pytest.raises(ValidationError):
        CashTransferCreate.model_validate({"amount": 10, "kind": "   "})
    with pytest.raises(ValidationError):
        CashTransferCreate.model_validate({"amount": 10, "kind": "wire"})


def test_cash_transfer_kind_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "xferKind" in accounting
    assert 'value="deposit"' in accounting
    assert 'value="withdrawal"' in accounting
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "transfer|deposit|withdrawal" in api or "Literal" in api
    assert "422" in api
