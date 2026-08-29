"""EmailVerifyConfirm.token ∈ EmailVerifyTokenValue OpenAPI honesty (BR-19)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app import emailer
from app import models as m
from app.schemas import EmailVerifyConfirm, EmailVerifyTokenValue
from app.security import hash_password

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(EmailVerifyTokenValue)


def test_email_verify_token_value_schema():
    assert _token.validate_python("  Tip255Token_abc-xyz  ") == "Tip255Token_abc-xyz"
    assert _token.validate_python("a" * 200) == "a" * 200
    for bad in ("", " ", "!!!", "http://evil", "a@b", "tok en", "a" * 201):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    ok = EmailVerifyConfirm.model_validate({"token": "  tip255-ok-token  "})
    assert ok.token == "tip255-ok-token"
    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        with pytest.raises(ValidationError):
            EmailVerifyConfirm.model_validate({"token": bad})
    with pytest.raises(ValidationError):
        EmailVerifyConfirm.model_validate({})


def test_email_verify_token_ui_and_docs():
    page = (ROOT / "frontend/app/verify-email/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Email verification token"' in page
    assert "trimmedToken" in page
    assert 'aria-label="Verify email"' in page
    assert "!token.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Email verify token OpenAPI" in agents
    assert "EmailVerifyTokenValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "EmailVerifyTokenValue" in docs
    assert "Email verification token" in docs


@pytest.mark.asyncio
async def test_email_verify_token_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    emailer.clear_dev_outbox()
    suffix = uuid4().hex[:8]
    email = f"tip255-{suffix}@alpha.example.com"

    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        resp = await ac.post("/api/v1/auth/verify-email", json={"token": bad})
        assert resp.status_code == 422, (bad, resp.text)

    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="Tip255 Unverified",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=False,
        is_active=True,
        permissions={},
    )
    db_session.add(user)
    await db_session.commit()

    resend = await ac.post(
        "/api/v1/auth/resend-verification",
        json={"email": email, "tenant_id": "alpha"},
    )
    assert resend.status_code == 200, resend.text
    token = resend.json()["data"].get("verification_token")
    assert token, "DEBUG/non-prod should echo verification_token for tests"

    ok = await ac.post(
        "/api/v1/auth/verify-email",
        json={"token": f"  {token}  "},
    )
    assert ok.status_code == 200, ok.text
