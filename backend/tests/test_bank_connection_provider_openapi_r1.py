"""Bank connection provider OpenAPI Literal (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import BankConnectionCreate, BankConnectionUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_bank_connection_provider_literal_schema():
    ok = BankConnectionCreate.model_validate(
        {"account_id": "a1", "provider": "http_json", "feed_url": "https://example.test/feed"}
    )
    assert ok.provider == "http_json"
    defaulted = BankConnectionCreate.model_validate({"account_id": "a1"})
    assert defaulted.provider == "mock"
    with pytest.raises(ValidationError):
        BankConnectionCreate.model_validate({"account_id": "a1", "provider": ""})
    with pytest.raises(ValidationError):
        BankConnectionCreate.model_validate({"account_id": "a1", "provider": "   "})
    with pytest.raises(ValidationError):
        BankConnectionCreate.model_validate({"account_id": "a1", "provider": "plaid"})

    bare = BankConnectionUpdate.model_validate({})
    assert bare.provider is None
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"provider": ""})
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"provider": "plaid"})


def test_bank_connection_provider_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "connProvider" in accounting
    assert 'value="mock"' in accounting
    assert 'value="http_json"' in accounting
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "mock|http_json" in api or "http_json" in api
    assert "Literal" in api
    assert "422" in api
