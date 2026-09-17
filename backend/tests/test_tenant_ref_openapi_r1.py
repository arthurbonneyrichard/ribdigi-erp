"""Login / password-reset / resend tenant_id ∈ TenantRefValue OpenAPI honesty (BR-19 / BR-1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    Login,
    PasswordResetRequest,
    ResendVerificationRequest,
    TenantRefValue,
)

ROOT = Path(__file__).resolve().parents[2]
_ref = TypeAdapter(TenantRefValue)
_UUID = "94b790f2-e6e8-4fcc-88ec-58a0e1787415"


def test_tenant_ref_value_schema():
    assert _ref.validate_python("  Tip256-co  ") == "tip256-co"
    assert _ref.validate_python(f"  {_UUID.upper()}  ") == _UUID
    assert _ref.validate_python("alpha") == "alpha"
    for bad in ("", " ", "!!!", "http://evil", "a@b", "a b", "X", "-bad", "a"):
        with pytest.raises(ValidationError):
            _ref.validate_python(bad)

    ok = Login.model_validate(
        {
            "email": "ok@example.com",
            "password": "SecurePass123!",
            "tenant_id": "  Tip256-Login  ",
        }
    )
    assert ok.tenant_id == "tip256-login"
    for bad in ("", "!!!", "http://evil", "a b", "X"):
        with pytest.raises(ValidationError):
            Login.model_validate(
                {
                    "email": "bad@example.com",
                    "password": "SecurePass123!",
                    "tenant_id": bad,
                }
            )
    with pytest.raises(ValidationError):
        Login.model_validate(
            {"email": "omit@example.com", "password": "SecurePass123!"}
        )

    pr = PasswordResetRequest.model_validate(
        {"email": "a@b.com", "tenant_id": f"  {_UUID}  "}
    )
    assert pr.tenant_id == _UUID
    with pytest.raises(ValidationError):
        PasswordResetRequest.model_validate({"email": "a@b.com", "tenant_id": "!!!"})

    rv = ResendVerificationRequest.model_validate(
        {"email": "a@b.com", "tenant_id": "  Alpha  "}
    )
    assert rv.tenant_id == "alpha"
    with pytest.raises(ValidationError):
        ResendVerificationRequest.model_validate(
            {"email": "a@b.com", "tenant_id": "not a slug"}
        )


def test_tenant_ref_ui_and_docs():
    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Login tenant"' in login
    assert "trimmedTenant" in login
    assert "Login tenant is required" in login
    forgot = (ROOT / "frontend/app/forgot-password/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Password reset tenant"' in forgot
    assert "trimmedTenant" in forgot
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Login tenant OpenAPI" in agents
    assert "TenantRefValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TenantRefValue" in docs
    assert "Login tenant" in docs


@pytest.mark.asyncio
async def test_tenant_ref_api_blank_invalid_422(client, seeded):
    ac, _seed = client

    for bad in ("", "!!!", "http://evil", "a b", "X", "-bad"):
        resp = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@alpha.example.com",
                "password": "SecurePass123!",
                "tenant_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok_slug = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "  Alpha  ",
        },
    )
    assert ok_slug.status_code == 200, ok_slug.text
    data = ok_slug.json()["data"]
    assert data.get("access_token") or data.get("requires_2fa")

    for bad in ("", "!!!", "http://evil", "a b"):
        pr = await ac.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "admin@alpha.example.com", "tenant_id": bad},
        )
        assert pr.status_code == 422, (bad, pr.text)

    pr_ok = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "admin@alpha.example.com", "tenant_id": "  alpha  "},
    )
    assert pr_ok.status_code == 200, pr_ok.text

    for bad in ("", "!!!", "not a slug"):
        rs = await ac.post(
            "/api/v1/auth/resend-verification",
            json={"email": "admin@alpha.example.com", "tenant_id": bad},
        )
        assert rs.status_code == 422, (bad, rs.text)
