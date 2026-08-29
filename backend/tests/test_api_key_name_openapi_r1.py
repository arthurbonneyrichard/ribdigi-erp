"""ApiKeyCreate.name OpenAPI honesty (BR-18.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ApiKeyCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_api_key_name_schema():
    ok = ApiKeyCreate.model_validate({"name": "  Integrator Bot  "})
    assert ok.name == "Integrator Bot"
    for bad in ("", " ", "a", "!!!", "http://evil", "@@", "x" * 121):
        with pytest.raises(ValidationError):
            ApiKeyCreate.model_validate({"name": bad})


def test_api_key_name_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="API key name"' in page
    assert "keyName.trim()" in page
    assert 'aria-label="Create API key"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "API key name OpenAPI" in agents
    assert "ApiKeyNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ApiKeyNameValue" in docs
    assert "API key name" in docs


@pytest.mark.asyncio
async def test_api_key_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "x"):
        r = await ac.post("/api/v1/api-keys", headers=headers, json={"name": bad})
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": f"  Tip141 Key {suffix}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip141 Key {suffix}"
    assert ok.json()["data"].get("api_key", "").startswith("rdk_")
