"""Subscription term_unit OpenAPI Literal (platform packages)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantSubscriptionAssign

ROOT = Path(__file__).resolve().parents[2]


def test_subscription_term_unit_literal_schema():
    ok = TenantSubscriptionAssign.model_validate(
        {"package_code": "starter", "term_value": 1, "term_unit": "years"}
    )
    assert ok.term_unit == "years"
    defaulted = TenantSubscriptionAssign.model_validate(
        {"package_code": "starter", "term_value": 6}
    )
    assert defaulted.term_unit == "months"

    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "starter", "term_value": 1, "term_unit": ""}
        )
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "starter", "term_value": 1, "term_unit": "   "}
        )
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "starter", "term_value": 1, "term_unit": "weeks"}
        )


def test_subscription_term_unit_ui_and_docs():
    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert "term_unit" in platform
    assert 'value="months"' in platform
    assert 'value="years"' in platform
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "term_unit" in api
    assert "Literal" in api
    assert "422" in api
