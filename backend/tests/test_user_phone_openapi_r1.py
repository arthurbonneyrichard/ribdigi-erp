"""UserCreate / UserUpdate.phone OpenAPI honesty (Users User phone)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import UserCreate, UserUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_user_phone_schema():
    create_omit = UserCreate.model_validate(
        {
            "email": "a@example.com",
            "full_name": "Ada",
            "password": "SecurePass123!",
        }
    )
    assert create_omit.phone is None
    create_ok = UserCreate.model_validate(
        {
            "email": "b@example.com",
            "full_name": "Bea",
            "password": "SecurePass123!",
            "phone": " +233241111111 ",
        }
    )
    assert create_ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate(
                {
                    "email": "c@example.com",
                    "full_name": "Cee",
                    "password": "SecurePass123!",
                    "phone": bad,
                }
            )

    patch_omit = UserUpdate.model_validate({})
    assert patch_omit.phone is None
    patch_ok = UserUpdate.model_validate({"phone": "+233200000001"})
    assert patch_ok.phone == "+233200000001"
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"phone": ""})
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"phone": "not-a-phone"})


def test_user_phone_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User phone"' in page
    assert "form.phone || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "User phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "User phone" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_user_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "phone-blank@alpha.example.com",
            "full_name": "Phone Blank",
            "password": "SecurePass123!",
            "role": "cashier",
            "phone": "",
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "phone-bad@alpha.example.com",
            "full_name": "Phone Bad",
            "password": "SecurePass123!",
            "role": "cashier",
            "phone": "not-a-phone",
        },
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "phone-ok@alpha.example.com",
            "full_name": "Phone Ok",
            "password": "SecurePass123!",
            "role": "cashier",
            "phone": "+233241111111",
        },
    )
    assert ok.status_code == 200, ok.text
    user = ok.json()["data"]["user"] if "user" in ok.json().get("data", {}) else ok.json()["data"]
    user_id = user["id"]
    assert user["phone"] == "+233241111111"

    patch_bad = await ac.patch(
        f"/api/v1/users/{user_id}", headers=admin, json={"phone": "123"}
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=admin,
        json={"phone": "+233200000099"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    patched = patch_ok.json()["data"]
    assert patched.get("phone") == "+233200000099" or patched.get("user", {}).get(
        "phone"
    ) == "+233200000099"
