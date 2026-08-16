"""PlatformStaffCreate/Update.role OpenAPI Literal."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PlatformStaffCreate, PlatformStaffUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_platform_staff_role_literal_schema():
    ok = PlatformStaffCreate.model_validate(
        {
            "email": "a@example.com",
            "full_name": "A",
            "password": "SecurePass123!",
            "role": "platform_finance",
        }
    )
    assert ok.role == "platform_finance"

    defaulted = PlatformStaffCreate.model_validate(
        {
            "email": "b@example.com",
            "full_name": "B",
            "password": "SecurePass123!",
        }
    )
    assert defaulted.role == "platform_support"

    coerced = PlatformStaffCreate.model_validate(
        {
            "email": "c@example.com",
            "full_name": "C",
            "password": "SecurePass123!",
            "role": "  Platform_Admin ",
        }
    )
    assert coerced.role == "platform_admin"

    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "d@example.com",
                "full_name": "D",
                "password": "SecurePass123!",
                "role": "",
            }
        )
    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "e@example.com",
                "full_name": "E",
                "password": "SecurePass123!",
                "role": "cashier",
            }
        )
    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "f@example.com",
                "full_name": "F",
                "password": "SecurePass123!",
                "role": "garbage_xyz",
            }
        )

    patch = PlatformStaffUpdate.model_validate({"role": "Platform_Support"})
    assert patch.role == "platform_support"
    with pytest.raises(ValidationError):
        PlatformStaffUpdate.model_validate({"role": ""})
    with pytest.raises(ValidationError):
        PlatformStaffUpdate.model_validate({"role": "company_admin"})


def test_platform_staff_role_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert "Create staff" in staff or "createStaff" in staff
    assert "role" in staff
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform staff create/update role OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PlatformStaffCreate" in docs or "create/patch `role`" in docs or "silent support from `\"\"` via former" in docs
