"""TenantProfileUpdate.phone OpenAPI honesty (PATCH /tenants/me — Company phone)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_profile_phone_schema():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.phone is None
    ok = TenantProfileUpdate.model_validate({"phone": " +233241111111 "})
    assert ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"phone": bad})


def test_company_phone_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company phone"' in page
    assert "Omit blank phone" in page or "trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "E164PhoneValue" in docs
    assert "Company phone" in docs


@pytest.mark.asyncio
async def test_company_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.patch("/api/v1/tenants/me", headers=admin, json={"phone": ""})
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        "/api/v1/tenants/me", headers=admin, json={"phone": "not-a-phone"}
    )
    assert garbage.status_code == 422, garbage.text

    short = await ac.patch(
        "/api/v1/tenants/me", headers=admin, json={"phone": "123"}
    )
    assert short.status_code == 422, short.text

    ok = await ac.patch(
        "/api/v1/tenants/me", headers=admin, json={"phone": "+233241111111"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["phone"] == "+233241111111"

    keep = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"company_name": seed["t1"].company_name},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["phone"] == "+233241111111"
