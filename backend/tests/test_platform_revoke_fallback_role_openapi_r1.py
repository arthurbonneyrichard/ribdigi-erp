"""PlatformRevokeAccess.fallback_role OpenAPI Literal."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PlatformRevokeAccess

ROOT = Path(__file__).resolve().parents[2]


def test_platform_revoke_fallback_role_literal_schema():
    ok = PlatformRevokeAccess.model_validate({"fallback_role": "cashier"})
    assert ok.fallback_role == "cashier"

    defaulted = PlatformRevokeAccess.model_validate({})
    assert defaulted.fallback_role == "company_admin"

    coerced = PlatformRevokeAccess.model_validate({"fallback_role": "  Accountant "})
    assert coerced.fallback_role == "accountant"

    with pytest.raises(ValidationError):
        PlatformRevokeAccess.model_validate({"fallback_role": ""})
    with pytest.raises(ValidationError):
        PlatformRevokeAccess.model_validate({"fallback_role": "   "})
    with pytest.raises(ValidationError):
        PlatformRevokeAccess.model_validate({"fallback_role": "platform_support"})
    with pytest.raises(ValidationError):
        PlatformRevokeAccess.model_validate({"fallback_role": "super_admin"})
    with pytest.raises(ValidationError):
        PlatformRevokeAccess.model_validate({"fallback_role": "garbage_xyz"})


def test_platform_revoke_fallback_role_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert "/revoke" in staff
    assert "fallback_role" in staff
    assert "company_admin" in staff
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'Literal["company_admin","store_manager","sales_officer","inventory_officer","accountant","cashier"]' in api
    assert "422" in api
