"""PlatformGrantAccess.role OpenAPI Literal."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PlatformGrantAccess

ROOT = Path(__file__).resolve().parents[2]


_USER = "11111111-2222-3333-4444-555555555555"


def test_platform_grant_role_literal_schema():
    ok = PlatformGrantAccess.model_validate(
        {"user_id": _USER, "role": "platform_finance"}
    )
    assert ok.role == "platform_finance"

    defaulted = PlatformGrantAccess.model_validate({"user_id": _USER})
    assert defaulted.role == "platform_support"

    coerced = PlatformGrantAccess.model_validate(
        {"user_id": _USER, "role": "  Platform_Admin "}
    )
    assert coerced.role == "platform_admin"

    with pytest.raises(ValidationError):
        PlatformGrantAccess.model_validate({"user_id": _USER, "role": ""})
    with pytest.raises(ValidationError):
        PlatformGrantAccess.model_validate({"user_id": _USER, "role": "   "})
    with pytest.raises(ValidationError):
        PlatformGrantAccess.model_validate({"user_id": _USER, "role": "cashier"})
    with pytest.raises(ValidationError):
        PlatformGrantAccess.model_validate({"user_id": _USER, "role": "garbage_xyz"})


def test_platform_grant_role_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert "grantRole" in staff
    assert "/platform/staff/grant" in staff
    assert "Grant as" in staff
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'Literal["super_admin","platform_owner","platform_admin","platform_support","platform_finance"]' in api
    assert "422" in api
