"""PasswordResetConfirm.token ∈ PasswordResetTokenValue OpenAPI honesty (BR-19)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app import emailer
from app.schemas import PasswordResetConfirm, PasswordResetTokenValue

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(PasswordResetTokenValue)


def test_password_reset_token_value_schema():
    assert _token.validate_python("  Tip254Token_abc-xyz  ") == "Tip254Token_abc-xyz"
    assert _token.validate_python("a" * 200) == "a" * 200
    for bad in ("", " ", "!!!", "http://evil", "a@b", "tok en", "a" * 201):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    ok = PasswordResetConfirm.model_validate(
        {"token": "  tip254-ok-token  ", "new_password": "SecurePass123!"}
    )
    assert ok.token == "tip254-ok-token"
    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        with pytest.raises(ValidationError):
            PasswordResetConfirm.model_validate(
                {"token": bad, "new_password": "SecurePass123!"}
            )
    with pytest.raises(ValidationError):
        PasswordResetConfirm.model_validate({"new_password": "SecurePass123!"})


def test_password_reset_token_ui_and_docs():
    page = (ROOT / "frontend/app/reset-password/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Password reset token"' in page
    assert "trimmedToken" in page
    assert 'aria-label="Update password"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Password reset token OpenAPI" in agents
    assert "PasswordResetTokenValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PasswordResetTokenValue" in docs
    assert "Password reset token" in docs


@pytest.mark.asyncio
async def test_password_reset_token_api_blank_invalid_422(client, seeded):
    ac, _seed = client
    emailer.clear_dev_outbox()
    suffix = uuid4().hex[:8]
    email = "cashier@alpha.example.com"

    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        resp = await ac.post(
            "/api/v1/auth/password-reset",
            json={"token": bad, "new_password": "SecurePass123!"},
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
        json={"token": f"  {token}  ", "new_password": f"Tip254Pass!{suffix[:4]}"},
    )
    assert ok.status_code == 200, ok.text
