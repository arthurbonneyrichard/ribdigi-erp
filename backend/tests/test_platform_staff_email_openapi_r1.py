"""PlatformStaffCreate.email OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PlatformStaffCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_staff_email_schema():
    ok = PlatformStaffCreate.model_validate(
        {
            "email": "  staff@example.com  ",
            "full_name": "Staff",
            "password": "SecurePass123!",
        }
    )
    assert str(ok.email) == "staff@example.com"

    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "abc",
                "full_name": "Staff",
                "password": "SecurePass123!",
            }
        )
    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "",
                "full_name": "Staff",
                "password": "SecurePass123!",
            }
        )
    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "not-an-email",
                "full_name": "Staff",
                "password": "SecurePass123!",
            }
        )
    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "ok@example.com",
                "full_name": "Staff",
                "password": "SecurePass123!",
                "bogus": True,
            }
        )


def test_platform_staff_email_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Platform staff email"' in staff
    assert 'aria-label="Create platform staff"' in staff
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform staff email OpenAPI" in agents
    assert "EmailStr" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PlatformStaffCreate" in docs
    assert "EmailStr" in docs


@pytest.mark.asyncio
async def test_platform_staff_email_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    short = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": "abc",
            "full_name": "Bad Short",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert short.status_code == 422, short.text

    blank = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": "",
            "full_name": "Bad Blank",
            "password": "SecurePass123!",
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": "not-an-email",
            "full_name": "Bad Garbage",
            "password": "SecurePass123!",
        },
    )
    assert garbage.status_code == 422, garbage.text

    extra = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": "ok@example.com",
            "full_name": "Extra",
            "password": "SecurePass123!",
            "unknown": 1,
        },
    )
    assert extra.status_code == 422, extra.text

    ok = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": "tip72-staff@example.com",
            "full_name": "Tip72 Staff",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["email"] == "tip72-staff@example.com"
    assert ok.json()["data"]["role"] == "platform_support"
