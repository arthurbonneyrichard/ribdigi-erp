"""TenantCreate.admin_password ∈ TenantAdminPasswordValue OpenAPI honesty (BR-1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import TenantAdminPasswordValue, TenantCreate

ROOT = Path(__file__).resolve().parents[2]
_password = TypeAdapter(TenantAdminPasswordValue)


def test_tenant_admin_password_value_schema():
    assert _password.validate_python("  Tip248Pass!  ") == "Tip248Pass!"
    assert _password.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "pass word", "a" * 129):
        with pytest.raises(ValidationError):
            _password.validate_python(bad)

    ok = TenantCreate.model_validate(
        {
            "company_name": "Tip248 Co",
            "slug": "tip248-co",
            "admin_email": "admin@tip248.example.com",
            "admin_password": "  SecurePass123!  ",
        }
    )
    assert ok.admin_password == "SecurePass123!"
    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        with pytest.raises(ValidationError):
            TenantCreate.model_validate(
                {
                    "company_name": "Bad Co",
                    "slug": "bad-co",
                    "admin_email": "bad@example.com",
                    "admin_password": bad,
                }
            )
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "No Password Co",
                "slug": "no-pass-co",
                "admin_email": "nopass@example.com",
            }
        )


def test_tenant_admin_password_ui_and_docs():
    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tenant admin password"' in platform
    assert "trimmedPassword" in platform
    assert 'aria-label="Create tenant"' in platform
    assert "!form.admin_password.trim()" in platform
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tenant admin password OpenAPI" in agents
    assert "TenantAdminPasswordValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TenantAdminPasswordValue" in docs
    assert "Tenant admin password" in docs


@pytest.mark.asyncio
async def test_tenant_admin_password_api_blank_invalid_422(client, seeded):
    ac, _seed = client
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "a@b", "pass word"):
        resp = await ac.post(
            "/api/v1/tenants",
            json={
                "company_name": f"Tip248 Bad {suffix}",
                "slug": f"tip248-bad-{suffix}-{abs(hash(bad)) % 10000}",
                "admin_email": f"bad-{suffix}-{abs(hash(bad)) % 10000}@tip248.example.com",
                "admin_password": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/tenants",
        json={
            "company_name": f"Tip248 Co {suffix}",
            "slug": f"tip248-{suffix}",
            "admin_email": f"admin-{suffix}@tip248.example.com",
            "admin_password": "  Tip248Pass!  ",
            "industry": "retail",
            "currency": "GHS",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["slug"] == f"tip248-{suffix}"
    assert "admin_password" not in data
    assert "password" not in data
