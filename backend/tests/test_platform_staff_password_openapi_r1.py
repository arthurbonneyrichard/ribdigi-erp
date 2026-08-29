"""PlatformStaffCreate.password ∈ PlatformStaffPasswordValue OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PlatformStaffCreate, PlatformStaffPasswordValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(PlatformStaffPasswordValue)


def test_platform_staff_password_value_schema():
    assert _password.validate_python("  Tip246Pass!  ") == "Tip246Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    ok = PlatformStaffCreate.model_validate(
        {
            "email": "ok@example.com",
            "full_name": "Ada Lovelace",
            "password": "  SecurePass123!  ",
        }
    )
    assert ok.password == "SecurePass123!"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            PlatformStaffCreate.model_validate(
                {
                    "email": "bad@example.com",
                    "full_name": "Bad Staff",
                    "password": bad,
                }
            )
    with pytest.raises(ValidationError):
        PlatformStaffCreate.model_validate(
            {
                "email": "omit@example.com",
                "full_name": "No Password",
            }
        )


def test_platform_staff_password_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Platform staff password"' in staff
    assert "trimmedPassword" in staff
    assert 'aria-label="Create platform staff"' in staff
    assert "!form.password.trim()" in staff
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform staff password OpenAPI" in agents
    assert "PlatformStaffPasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PlatformStaffPasswordValue" in docs
    assert "Platform staff password" in docs


@pytest.mark.asyncio
async def test_platform_staff_password_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        resp = await ac.post(
            "/api/v1/platform/staff",
            headers=admin,
            json={
                "email": f"bad-pass-{suffix}-{abs(hash(bad)) % 10000}@example.com",
                "full_name": f"Tip246 Bad {suffix}",
                "password": bad,
                "role": "platform_support",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"tip246-{suffix}@example.com",
            "full_name": f"Tip246 Staff {suffix}",
            "password": "  Tip246Pass!  ",
            "role": "platform_support",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["email"] == f"tip246-{suffix}@example.com"
    assert "password" not in ok.json()["data"]
