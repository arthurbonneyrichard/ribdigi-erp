"""TwoFactorConfirm / Verify / Disable.code + Login.totp_code OpenAPI (BR-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    Login,
    TwoFactorCodeValue,
    TwoFactorConfirm,
    TwoFactorDisable,
    TwoFactorVerify,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(TwoFactorCodeValue)


def test_two_factor_code_value_schema():
    assert _code.validate_python("  123456  ") == "123456"
    assert _code.validate_python("AB12-CD34") == "AB12-CD34"
    for bad in ("", " ", "!!!", "http://evil", "@@", "abc", "12"):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    confirm = TwoFactorConfirm.model_validate({"code": "  654321  "})
    assert confirm.code == "654321"
    with pytest.raises(ValidationError):
        TwoFactorConfirm.model_validate({"code": ""})
    with pytest.raises(ValidationError):
        TwoFactorConfirm.model_validate({"code": "!!!"})
    with pytest.raises(ValidationError):
        TwoFactorConfirm.model_validate({})

    verify = TwoFactorVerify.model_validate(
        {"challenge_token": "tok", "code": "  111222  "}
    )
    assert verify.code == "111222"
    with pytest.raises(ValidationError):
        TwoFactorVerify.model_validate({"challenge_token": "tok", "code": "http://x"})

    disable = TwoFactorDisable.model_validate(
        {"password": "SecretPass1!", "code": "backup1"}
    )
    assert disable.code == "backup1"
    with pytest.raises(ValidationError):
        TwoFactorDisable.model_validate({"password": "SecretPass1!", "code": "@@"})

    login_omit = Login.model_validate(
        {
            "email": "a@b.com",
            "password": "x",
            "tenant_id": "t1",
        }
    )
    assert login_omit.totp_code is None
    login_ok = Login.model_validate(
        {
            "email": "a@b.com",
            "password": "x",
            "tenant_id": "t1",
            "totp_code": "  998877  ",
        }
    )
    assert login_ok.totp_code == "998877"
    with pytest.raises(ValidationError):
        Login.model_validate(
            {
                "email": "a@b.com",
                "password": "x",
                "tenant_id": "t1",
                "totp_code": "",
            }
        )
    with pytest.raises(ValidationError):
        Login.model_validate(
            {
                "email": "a@b.com",
                "password": "x",
                "tenant_id": "t1",
                "totp_code": "!!!",
            }
        )


def test_two_factor_code_ui_and_docs():
    security = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="2FA setup code"' in security
    assert 'aria-label="2FA code"' in security
    assert 'aria-label="Confirm 2FA setup"' in security
    assert 'aria-label="Regenerate backup codes"' in security
    assert 'aria-label="Disable 2FA"' in security
    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="2FA code"' in login
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "2FA code OpenAPI" in agents
    assert "TwoFactorCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TwoFactorCodeValue" in docs
    assert "2FA setup code" in docs


@pytest.mark.asyncio
async def test_two_factor_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )

    for bad in ("", "!!!", "http://evil", "abc", "12"):
        r = await ac.post(
            "/api/v1/auth/2fa/confirm",
            headers=headers,
            json={"code": bad},
        )
        assert r.status_code == 422, (bad, r.text)

        r2 = await ac.post(
            "/api/v1/auth/2fa/backup-codes",
            headers=headers,
            json={"code": bad},
        )
        assert r2.status_code == 422, (bad, r2.text)

        r3 = await ac.post(
            "/api/v1/auth/2fa/disable",
            headers=headers,
            json={"password": "AdminPass123!", "code": bad},
        )
        assert r3.status_code == 422, (bad, r3.text)

        r4 = await ac.post(
            "/api/v1/auth/2fa/verify",
            json={"challenge_token": "not-a-real-token", "code": bad},
        )
        assert r4.status_code == 422, (bad, r4.text)

        r5 = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@alpha.example.com",
                "password": "AdminPass123!",
                "tenant_id": "alpha",
                "totp_code": bad,
            },
        )
        assert r5.status_code == 422, (bad, r5.text)

    # well-shaped code → not schema 422 (may fail auth later)
    shaped = await ac.post(
        "/api/v1/auth/2fa/confirm",
        headers=headers,
        json={"code": "  123456  "},
    )
    assert shaped.status_code != 422, shaped.text
