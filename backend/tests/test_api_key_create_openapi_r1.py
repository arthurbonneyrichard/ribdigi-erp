"""POST /api-keys typed ApiKeyCreate OpenAPI (BR-18.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ApiKeyCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_api_key_create_schema_forbid_and_bounds():
    ok = ApiKeyCreate.model_validate({"name": "  Integrator  "})
    assert ok.name == "Integrator"
    assert ok.permissions is None
    assert ok.expires_at is None

    with_exp = ApiKeyCreate.model_validate(
        {
            "name": "With expiry",
            "expires_at": "2030-01-15T12:00:00Z",
            "permissions": {"Inventory": ["READ", "write"]},
        }
    )
    assert with_exp.expires_at == datetime(2030, 1, 15, 12, 0, 0)
    assert with_exp.permissions == {"inventory": ["read", "write"]}

    # Empty permissions map still means defaults (historical create_key behavior).
    empty_perms = ApiKeyCreate.model_validate({"name": "Defaults", "permissions": {}})
    assert empty_perms.permissions is None

    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({"name": "x", "unknown_field": 1})
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({})
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({"name": "a"})
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({"name": "x" * 121})
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({"name": "bad", "expires_at": "not-a-date"})
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate(
            {"name": "bad", "permissions": {"not_a_module": ["read"]}}
        )
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate(
            {"name": "bad", "permissions": {"inventory": ["execute"]}}
        )
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({"name": "bad", "permissions": {"inventory": []}})


def test_api_key_create_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="API key name"' in page
    assert 'aria-label="API key expiry"' in page
    assert 'aria-label="Create API key"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "API key create OpenAPI" in agents
    assert "ApiKeyCreate" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ApiKeyCreate" in docs
    assert "extra=forbid" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_api_key_create_api_unknown_422(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    unknown = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Probe", "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    short = await ac.post("/api/v1/api-keys", headers=headers, json={"name": "x"})
    assert short.status_code == 422, short.text

    omit = await ac.post("/api/v1/api-keys", headers=headers, json={})
    assert omit.status_code == 422, omit.text

    bad_exp = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Probe", "expires_at": "yesterday"},
    )
    assert bad_exp.status_code == 422, bad_exp.text

    bad_mod = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Probe", "permissions": {"spaceship": ["read"]}},
    )
    assert bad_mod.status_code == 422, bad_mod.text

    bad_act = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Probe", "permissions": {"inventory": ["launch"]}},
    )
    assert bad_act.status_code == 422, bad_act.text

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={
            "name": "Create OpenAPI probe",
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z",
            "permissions": {"sales": ["read"]},
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["name"] == "Create OpenAPI probe"
    assert data["permissions"] == {"sales": ["read"]}
    assert data.get("api_key", "").startswith("rdk_")

    defaulted = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Defaults probe", "permissions": {}},
    )
    assert defaulted.status_code == 200, defaulted.text
    perms = defaulted.json()["data"]["permissions"]
    assert "inventory" in perms and "read" in perms["inventory"]
