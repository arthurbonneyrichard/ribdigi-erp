"""AccountCreate account_type / liquid_kind OpenAPI Literals (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AccountCreate

ROOT = Path(__file__).resolve().parents[2]


def test_account_type_liquid_kind_literal_schema():
    ok = AccountCreate.model_validate(
        {"code": "6100", "name": "Misc", "account_type": "expense"}
    )
    assert ok.account_type == "expense"
    assert ok.liquid_kind is None
    defaulted = AccountCreate.model_validate({"code": "1001", "name": "Petty", "liquid_kind": "cash"})
    assert defaulted.account_type == "asset"
    assert defaulted.liquid_kind == "cash"
    bare = AccountCreate.model_validate({"code": "1999", "name": "Other"})
    assert bare.account_type == "asset"
    assert bare.liquid_kind is None

    with pytest.raises(ValidationError):
        AccountCreate.model_validate({"code": "1", "name": "x", "account_type": ""})
    with pytest.raises(ValidationError):
        AccountCreate.model_validate({"code": "1", "name": "x", "account_type": "revenue"})
    with pytest.raises(ValidationError):
        AccountCreate.model_validate({"code": "1", "name": "x", "liquid_kind": ""})
    with pytest.raises(ValidationError):
        AccountCreate.model_validate({"code": "1", "name": "x", "liquid_kind": "wallet"})


def test_account_type_liquid_kind_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "newAcctKind" in accounting
    assert 'value="cash"' in accounting
    assert 'value="bank"' in accounting
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "liquid_kind" in api
    assert "account_type" in api
    assert "Literal" in api
    assert "422" in api
