"""Login.password ∈ LoginPasswordValue OpenAPI honesty (BR-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import Login, LoginPasswordValue

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(LoginPasswordValue)


def test_login_password_value_schema():
    assert _password.validate_python("  Tip252Pass!  ") == "Tip252Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    ok = Login.model_validate(
        {
            "email": "ok@example.com",
            "password": "  SecurePass123!  ",
            "tenant_id": "alpha",
        }
    )
    assert ok.password == "SecurePass123!"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            Login.model_validate(
                {
                    "email": "bad@example.com",
                    "password": bad,
                    "tenant_id": "alpha",
                }
            )
    with pytest.raises(ValidationError):
        Login.model_validate({"email": "omit@example.com", "tenant_id": "alpha"})


def test_login_password_ui_and_docs():
    page = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Login password"' in page
    assert "trimmedPassword" in page
    assert "!trimmedPassword" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Login password OpenAPI" in agents
    assert "LoginPasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "LoginPasswordValue" in docs
    assert "Login password" in docs


@pytest.mark.asyncio
async def test_login_password_api_blank_invalid_422(client, seeded):
    ac, _seed = client

    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        resp = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@alpha.example.com",
                "password": bad,
                "tenant_id": "alpha",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "  SecurePass123!  ",
            "tenant_id": "alpha",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data.get("access_token") or data.get("requires_2fa")
