"""Subscription package_code OpenAPI Literal (platform packages)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantSubscriptionAssign

ROOT = Path(__file__).resolve().parents[2]


def test_subscription_package_code_literal_schema():
    ok = TenantSubscriptionAssign.model_validate(
        {"package_code": "starter", "term_value": 1, "term_unit": "months"}
    )
    assert ok.package_code == "starter"

    coerced = TenantSubscriptionAssign.model_validate(
        {"package_code": "  Professional ", "term_value": 12}
    )
    assert coerced.package_code == "professional"

    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "", "term_value": 1}
        )
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "   ", "term_value": 1}
        )
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "gold", "term_value": 1}
        )
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "garbage_xyz", "term_value": 1}
        )


def test_subscription_package_code_ui_and_docs():
    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert "package_code" in platform
    assert "packages.map" in platform
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'Literal["trial","starter","professional","enterprise"]' in api
    assert "422" in api
