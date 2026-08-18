"""ProfileUpdate.phone OpenAPI honesty (PATCH /me — Company Profile phone)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_profile_update_phone_schema():
    omit = ProfileUpdate.model_validate({})
    assert omit.phone is None
    ok = ProfileUpdate.model_validate({"phone": " +233241111111 "})
    assert ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            ProfileUpdate.model_validate({"phone": bad})


def test_profile_phone_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Profile phone for SMS test"' in page
    assert 'aria-label="Save my phone"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Profile phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ProfileUpdate" in docs or "Profile phone" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_profile_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch("/api/v1/me", headers=admin, json={"phone": ""})
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/me", headers=admin, json={"phone": "not-a-phone"}
    )
    assert garbage.status_code == 422, garbage.text

    short = await ac.patch("/api/v1/me", headers=admin, json={"phone": "123"})
    assert short.status_code == 422, short.text

    ok = await ac.patch(
        "/api/v1/me", headers=admin, json={"phone": "+233241111111"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["phone"] == "+233241111111"

    # omit phone → no change
    keep = await ac.patch(
        "/api/v1/me", headers=admin, json={"full_name": "Alpha Super"}
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["phone"] == "+233241111111"
