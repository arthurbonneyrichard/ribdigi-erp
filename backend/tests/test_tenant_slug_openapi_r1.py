"""TenantCreate.slug ∈ TenantSlugValue OpenAPI (BR-1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import TenantCreate, TenantSlugValue

ROOT = Path(__file__).resolve().parents[2]
_slug = TypeAdapter(TenantSlugValue)


def test_tenant_slug_value_schema():
    assert _slug.validate_python("  Tip-235a  ") == "tip-235a"
    assert _slug.validate_python("  Good-Slug-01  ") == "good-slug-01"
    for bad in ("", " ", "!!!", "a b", "http://evil", "@@", "X", "-bad", "a" * 81):
        with pytest.raises(ValidationError):
            _slug.validate_python(bad)

    ok = TenantCreate.model_validate(
        {
            "company_name": "Tip 235 Co",
            "slug": "  Tip-235-co  ",
            "admin_email": "admin@tip235.example.com",
            "admin_password": "SecurePass123!",
        }
    )
    assert ok.slug == "tip-235-co"
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "Tip 235 Co",
                "slug": "!!!",
                "admin_email": "admin@tip235.example.com",
                "admin_password": "SecurePass123!",
            }
        )
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "Tip 235 Co",
                "slug": "",
                "admin_email": "admin@tip235.example.com",
                "admin_password": "SecurePass123!",
            }
        )


def test_tenant_slug_ui_and_docs():
    page = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tenant slug"' in page
    assert "slug: form.slug.trim().toLowerCase()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tenant slug OpenAPI" in agents
    assert "TenantSlugValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TenantSlugValue" in docs
    assert "Tenant slug" in docs


@pytest.mark.asyncio
async def test_tenant_slug_api_blank_invalid_422(client):
    ac, _seed = client
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "a b", "http://evil.example/p", "X", "-bad"):
        r = await ac.post(
            "/api/v1/tenants",
            json={
                "company_name": f"TIP235 Bad {suffix}",
                "slug": bad,
                "industry": "retail",
                "currency": "GHS",
                "admin_email": f"bad-{suffix}@tip235.example.com",
                "admin_password": "SecurePass123!",
            },
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/tenants",
        json={
            "company_name": f"TIP235 Hello {suffix}",
            "slug": f"  Tip235-{suffix}  ",
            "industry": "retail",
            "currency": "GHS",
            "admin_email": f"ok-{suffix}@tip235.example.com",
            "admin_password": "SecurePass123!",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["slug"] == f"tip235-{suffix}"
