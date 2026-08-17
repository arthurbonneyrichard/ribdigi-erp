"""GET /api-keys status Query OpenAPI Literal + Integrations manage filter (BR-18.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ApiKeyStatusFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_api_key_status_filter_literal_schema():
    adapter = TypeAdapter(ApiKeyStatusFilterValue)
    assert adapter.validate_python("active") == "active"
    assert adapter.validate_python("  Revoked ") == "revoked"
    assert adapter.validate_python("EXPIRED") == "expired"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("disabled")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_api_key_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert "apiKeyManageFilter" in page
    assert "managedKeys" in page
    assert 'aria-label="API key status filter"' in page
    assert 'value="revoked"' in page
    assert 'value="expired"' in page
    assert "No API keys for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "API key status Query OpenAPI" in agents
    assert "apiKeyManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "api-keys" in docs
    assert "422" in docs
    assert "apiKeyManageFilter" in docs or "API key status filter" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_api_key_status_filter_api_blank_invalid_422(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    blank = await ac.get("/api/v1/api-keys?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/api-keys?status=disabled", headers=headers)
    assert bad.status_code == 422, bad.text

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Status filter probe"},
    )
    assert created.status_code == 200, created.text
    key_id = created.json()["data"]["id"]

    active = await ac.get("/api/v1/api-keys?status=Active", headers=headers)
    assert active.status_code == 200, active.text
    assert any(r["id"] == key_id for r in active.json()["data"])
    assert all(r["status"] == "active" for r in active.json()["data"])

    revoked = await ac.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert revoked.status_code == 200, revoked.text

    only_revoked = await ac.get("/api/v1/api-keys?status=revoked", headers=headers)
    assert only_revoked.status_code == 200, only_revoked.text
    assert any(r["id"] == key_id for r in only_revoked.json()["data"])
    assert all(r["status"] == "revoked" for r in only_revoked.json()["data"])

    omit = await ac.get("/api/v1/api-keys", headers=headers)
    assert omit.status_code == 200, omit.text
