"""ProfileUpdate.full_name ∈ UserFullNameValue OpenAPI (BR-19)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_profile_full_name_schema():
    omit = ProfileUpdate.model_validate({})
    assert omit.full_name is None
    ok = ProfileUpdate.model_validate({"full_name": "  Tip229 User  "})
    assert ok.full_name == "Tip229 User"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ProfileUpdate.model_validate({"full_name": bad})


def test_profile_full_name_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Profile full name"' in page
    assert 'aria-label="Save my profile"' in page
    assert "profileFullName.trim()" in page
    assert "body.full_name = trimmedName" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Profile full name OpenAPI" in agents
    assert "UserFullNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Profile full name" in docs
    assert "UserFullNameValue" in docs


@pytest.mark.asyncio
async def test_profile_full_name_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.patch("/api/v1/me", headers=headers, json={"full_name": bad})
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.patch(
        "/api/v1/me",
        headers=headers,
        json={"full_name": f"  Tip229 OK {suffix}  "},
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["full_name"] == f"Tip229 OK {suffix}"
