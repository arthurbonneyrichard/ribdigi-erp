"""UserCreate / UserUpdate.password ∈ UserPasswordValue OpenAPI honesty (BR-3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UserCreate, UserPasswordValue, UserUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(UserPasswordValue)


def test_user_password_value_schema():
    assert _password.validate_python("  Tip247Pass!  ") == "Tip247Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    ok = UserCreate.model_validate(
        {
            "email": "ok@example.com",
            "full_name": "Ada Lovelace",
            "password": "  SecurePass123!  ",
        }
    )
    assert ok.password == "SecurePass123!"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate(
                {
                    "email": "bad@example.com",
                    "full_name": "Bad User",
                    "password": bad,
                }
            )
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "omit@example.com",
                "full_name": "No Password",
            }
        )

    patch_omit = UserUpdate.model_validate({})
    assert patch_omit.password is None
    patch_ok = UserUpdate.model_validate({"password": "  SecurePass123!  "})
    assert patch_ok.password == "SecurePass123!"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"password": bad})


def test_user_password_ui_and_docs():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User password"' in users
    assert "trimmedPassword" in users
    assert 'aria-label="Create user"' in users
    assert "!form.password.trim()" in users
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "User password OpenAPI" in agents
    assert "UserPasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UserPasswordValue" in docs
    assert "User password" in docs


@pytest.mark.asyncio
async def test_user_password_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        resp = await ac.post(
            "/api/v1/users",
            headers=admin,
            json={
                "email": f"bad-pass-{suffix}-{abs(hash(bad)) % 10000}@alpha.example.com",
                "full_name": "Bad Password User",
                "password": bad,
                "role": "cashier",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"tip247-{suffix}@alpha.example.com",
            "full_name": f"Tip247 User {suffix}",
            "password": "  Tip247Pass!  ",
            "role": "cashier",
        },
    )
    assert ok.status_code == 200, ok.text
    user = ok.json()["data"].get("user") or ok.json()["data"]
    uid = user["id"]

    for bad in ("", "!!!", "http://evil"):
        patch = await ac.patch(
            f"/api/v1/users/{uid}",
            headers=admin,
            json={"password": bad},
        )
        assert patch.status_code == 422, (bad, patch.text)
