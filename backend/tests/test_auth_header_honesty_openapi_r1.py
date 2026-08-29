"""OpenAPI honesty tips #639–#644: residual aria + auth header Values."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ApiKeyHeaderValue, UuidIdValue
from app import security as security_mod
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_auth_header_aria_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Cash drawer store aria OpenAPI",
        "Edit account select aria OpenAPI",
        "X-Tenant-ID header OpenAPI",
        "X-API-Key header OpenAPI",
        "Multi-tenant headers docs honesty OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    appendix = docs.split("## Appendix B: Multi-Tenant Headers")[1].split("##")[0]
    assert "tenant UUID" in appendix or "JWT/key tenant UUID" in appendix or "UuidIdValue" in appendix
    assert "tenant_abc123" in appendix  # called out as rejected slug example
    assert "ApiKeyHeaderValue" in docs
    assert "UuidIdValue" in appendix

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash drawer store"' in stores

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Edit account"' in accounting

    src = inspect.getsource(security_mod.current_claims)
    assert "UuidIdValue" in src
    assert "ApiKeyHeaderValue" in src


def test_api_key_header_value_rejects_garbage():
    ta = TypeAdapter(ApiKeyHeaderValue)
    assert ta.validate_python("rdk_abcDEF123").startswith("rdk_")
    for bad in ("", "   ", "!!!", "http://evil", "Bearer rdk_x", "not_rdk_key", "rdk_"):
        with pytest.raises(ValidationError):
            ta.validate_python(bad)


def test_uuid_id_value_rejects_slug():
    ta = TypeAdapter(UuidIdValue)
    with pytest.raises(ValidationError):
        ta.validate_python("alpha")
    with pytest.raises(ValidationError):
        ta.validate_python("tenant_abc123")


@pytest.mark.asyncio
async def test_x_tenant_id_slug_is_422(client):
    ac, seed = client
    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    r = await ac.get(
        "/api/v1/products",
        headers={**headers, "X-Tenant-ID": "alpha"},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_x_tenant_id_blank_is_422(client):
    ac, _seed = client
    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    r = await ac.get(
        "/api/v1/products",
        headers={**headers, "X-Tenant-ID": "   "},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_x_api_key_garbage_is_422(client):
    ac, seed = client
    r = await ac.get(
        "/api/v1/products",
        headers={"X-API-Key": "!!!", "X-Tenant-ID": seed["t1"].id},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_x_api_key_non_rdk_is_422(client):
    ac, seed = client
    r = await ac.get(
        "/api/v1/products",
        headers={"X-API-Key": "sk_live_not_ours", "X-Tenant-ID": seed["t1"].id},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_matching_x_tenant_uuid_still_ok(client):
    ac, seed = client
    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    # auth_headers already sets X-Tenant-ID to UUID
    assert headers.get("X-Tenant-ID") == seed["t1"].id
    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code == 200, r.text
