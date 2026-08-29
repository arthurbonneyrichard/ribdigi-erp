"""ApiKeyCreate.expires_at OpenAPI honesty (IsoDateQueryValue + parse_datetime)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.reports import parse_datetime
from app.schemas import ApiKeyCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_api_key_expires_at_schema():
    omit = ApiKeyCreate.model_validate({"name": "No expiry"})
    assert omit.expires_at is None
    ok = ApiKeyCreate.model_validate({"name": "Dated", "expires_at": " 2030-01-15 "})
    assert ok.expires_at == "2030-01-15"
    iso = ApiKeyCreate.model_validate(
        {"name": "Timed", "expires_at": "2030-01-15T12:30:00Z"}
    )
    assert iso.expires_at == "2030-01-15T12:30:00Z"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            ApiKeyCreate.model_validate({"name": "bad", "expires_at": bad})


def test_api_key_expires_at_parse_datetime_keeps_clock():
    assert parse_datetime(None) is None
    assert parse_datetime("2030-01-15").hour == 0
    dt = parse_datetime("2030-01-15T12:30:00Z")
    assert dt is not None
    assert dt.hour == 12 and dt.minute == 30
    assert dt.tzinfo is None


def test_api_key_expires_at_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="API key expiry"' in page
    assert "keyExpires.trim()" in page
    assert "YYYY-MM-DD or ISO datetime" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "API key expires_at OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    assert "parse_datetime" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "API key expiry" in docs
    assert "IsoDateQueryValue" in docs
    assert "parse_datetime" in docs


@pytest.mark.asyncio
async def test_api_key_expires_at_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            "/api/v1/api-keys",
            headers=headers,
            json={"name": f"Tip114 {uuid4().hex[:6]}", "expires_at": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={
            "name": f"Tip114 ok {uuid4().hex[:6]}",
            "expires_at": "2030-06-15T14:45:00Z",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert str(data.get("expires_at") or "").startswith("2030-06-15T14:45:00")
    assert data.get("api_key", "").startswith("rdk_")

    omit = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": f"Tip114 omit {uuid4().hex[:6]}"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("expires_at") in (None, "")
