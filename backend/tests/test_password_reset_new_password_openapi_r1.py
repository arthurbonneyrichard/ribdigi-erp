"""PasswordResetConfirm.new_password ∈ PasswordResetNewPasswordValue OpenAPI honesty (BR-19)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app import emailer
from app.schemas import PasswordResetConfirm, PasswordResetNewPasswordValue

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(PasswordResetNewPasswordValue)


def test_password_reset_new_password_value_schema():
    assert _password.validate_python("  Tip250Pass!  ") == "Tip250Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    ok = PasswordResetConfirm.model_validate(
        {"token": "tok", "new_password": "  SecurePass123!  "}
    )
    assert ok.new_password == "SecurePass123!"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            PasswordResetConfirm.model_validate({"token": "tok", "new_password": bad})
    with pytest.raises(ValidationError):
        PasswordResetConfirm.model_validate({"token": "tok"})


def test_password_reset_new_password_ui_and_docs():
    page = (ROOT / "frontend/app/reset-password/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Password reset new password"' in page
    assert "trimmedPassword" in page
    assert 'aria-label="Update password"' in page
    assert "!password.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Password reset new_password OpenAPI" in agents
    assert "PasswordResetNewPasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PasswordResetNewPasswordValue" in docs
    assert "Password reset new password" in docs


@pytest.mark.asyncio
async def test_password_reset_new_password_api_blank_invalid_422(client, seeded):
    ac, seed = client
    emailer.clear_dev_outbox()
    suffix = uuid4().hex[:8]
    email = "mgr@alpha.example.com"

    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        resp = await ac.post(
            "/api/v1/auth/password-reset",
            json={"token": f"tip250-bad-{suffix}", "new_password": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    req = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": email, "tenant_id": "alpha"},
    )
    assert req.status_code == 200, req.text
    token = req.json()["data"].get("reset_token")
    assert token, "DEBUG/non-prod should echo reset_token for tests"

    ok = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": token, "new_password": "  Tip250Pass!  "},
    )
    assert ok.status_code == 200, ok.text
