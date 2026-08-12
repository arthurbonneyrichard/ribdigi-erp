"""Tenant API keys for integration auth (BR-18.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import catalog_meta as catalog_meta_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_api_key_create_auth_revoke(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={
            "name": "ERP integrator",
            "permissions": {"inventory": ["read"], "sales": ["read"]},
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["api_key"].startswith("rdk_")
    assert body["secret_shown_once"] is True
    assert body["key_prefix"]
    key_id = body["id"]
    secret = body["api_key"]

    listed = await ac.get("/api/v1/api-keys", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()["data"]
    assert any(r["id"] == key_id for r in rows)
    assert all("api_key" not in r for r in rows)

    products = await ac.get(
        "/api/v1/products",
        headers={"X-API-Key": secret, "X-Tenant-ID": seed["t1"].id},
    )
    assert products.status_code == 200, products.text

    products_bearer = await ac.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert products_bearer.status_code == 200, products_bearer.text

    denied = await ac.post(
        "/api/v1/products",
        headers={"X-API-Key": secret},
        json={"name": "Nope", "sku": "NOPE-1", "selling_price": 1, "cost_price": 1},
    )
    assert denied.status_code == 403

    revoked = await ac.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["status"] == "revoked"

    after = await ac.get("/api/v1/products", headers={"X-API-Key": secret})
    assert after.status_code == 401

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.entity == "api_key",
                m.AuditLog.entity_id == key_id,
            )
        )
    ).scalars().all()
    actions = {a.action for a in audit}
    assert "api_key_create" in actions
    assert "api_key_revoke" in actions


@pytest.mark.asyncio
async def test_api_key_cross_tenant_header_blocked(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Scoped", "permissions": {"inventory": ["read"]}},
    )
    assert created.status_code == 200, created.text
    secret = created.json()["data"]["api_key"]
    blocked = await ac.get(
        "/api/v1/products",
        headers={"X-API-Key": secret, "X-Tenant-ID": seed["t2"].id},
    )
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_api_key_rejects_invalid_module(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    bad = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Bad", "permissions": {"not_a_module": ["read"]}},
    )
    assert bad.status_code == 400
