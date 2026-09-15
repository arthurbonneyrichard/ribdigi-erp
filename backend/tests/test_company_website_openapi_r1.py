"""TenantProfileUpdate.website OpenAPI honesty (PATCH /tenants/me — Company website)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_profile_website_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.website is None
    ok = TenantProfileUpdate.model_validate(
        {"website": "  https://acme.example.com/about  "}
    )
    assert ok.website == "https://acme.example.com/about"
    local = TenantProfileUpdate.model_validate(
        {"website": "http://localhost:3000"}
    )
    assert local.website.startswith("http://localhost")
    for bad in (
        "",
        " ",
        "not-a-url",
        "ftp://example.com",
        "www.example.com",
        "example.com",
        "http://example.com",
    ):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"website": bad})


def test_company_website_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company website"' in page
    assert "Omit blank website" in page or "tenant.website" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company website OpenAPI" in agents
    assert "WebhookUrlValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Company website" in docs
    assert "WebhookUrlValue" in docs


@pytest.mark.asyncio
async def test_company_website_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch("/api/v1/tenants/me", headers=admin, json={"website": ""})
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/tenants/me", headers=admin, json={"website": "not-a-url"}
    )
    assert garbage.status_code == 422, garbage.text

    bare = await ac.patch(
        "/api/v1/tenants/me", headers=admin, json={"website": "www.example.com"}
    )
    assert bare.status_code == 422, bare.text

    http_remote = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"website": "http://example.com"},
    )
    assert http_remote.status_code == 422, http_remote.text

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"website": "https://acme.example.com"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["website"] == "https://acme.example.com"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": seed["t1"].company_name},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["website"] == "https://acme.example.com"
