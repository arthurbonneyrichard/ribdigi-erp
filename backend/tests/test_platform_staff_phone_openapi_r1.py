"""PlatformStaffCreate / PlatformStaffUpdate.phone OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PlatformStaffCreate, PlatformStaffUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_staff_phone_schema():
    create_omit = PlatformStaffCreate.model_validate(
        {
            "email": "omit@example.com",
            "full_name": "Omit",
            "password": "SecurePass123!",
        }
    )
    assert create_omit.phone is None
    create_ok = PlatformStaffCreate.model_validate(
        {
            "email": "ok@example.com",
            "full_name": "Ok",
            "password": "SecurePass123!",
            "phone": " +233241111111 ",
        }
    )
    assert create_ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            PlatformStaffCreate.model_validate(
                {
                    "email": "bad@example.com",
                    "full_name": "Bad",
                    "password": "SecurePass123!",
                    "phone": bad,
                }
            )

    patch_omit = PlatformStaffUpdate.model_validate({})
    assert patch_omit.phone is None
    patch_ok = PlatformStaffUpdate.model_validate({"phone": "+233200000001"})
    assert patch_ok.phone == "+233200000001"
    with pytest.raises(ValidationError):
        PlatformStaffUpdate.model_validate({"phone": ""})
    with pytest.raises(ValidationError):
        PlatformStaffUpdate.model_validate({"phone": "not-a-phone"})


def test_platform_staff_phone_ui_and_docs():
    staff = (ROOT / "frontend/app/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Platform staff phone"' in staff
    assert "form.phone.trim() || null" in staff
    assert "E.164" in staff
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Platform staff phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Platform staff phone" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_platform_staff_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"blank-phone-{uuid4().hex[:8]}@example.com",
            "full_name": "Blank Phone",
            "password": "SecurePass123!",
            "role": "platform_support",
            "phone": "",
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"garbage-phone-{uuid4().hex[:8]}@example.com",
            "full_name": "Garbage Phone",
            "password": "SecurePass123!",
            "role": "platform_support",
            "phone": "not-a-phone",
        },
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"ok-phone-{uuid4().hex[:8]}@example.com",
            "full_name": "Ok Phone",
            "password": "SecurePass123!",
            "role": "platform_support",
            "phone": "+233241111111",
        },
    )
    assert ok.status_code == 200, ok.text
    row = ok.json()["data"]
    assert row["phone"] == "+233241111111"
    staff_id = row["id"]

    patch_bad = await ac.patch(
        f"/api/v1/platform/staff/{staff_id}",
        headers=admin,
        json={"phone": "123"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/platform/staff/{staff_id}",
        headers=admin,
        json={"phone": "+233200000099"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["phone"] == "+233200000099"

    omit = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"omit-phone-{uuid4().hex[:8]}@example.com",
            "full_name": "Omit Phone",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("phone") in (None, "")
