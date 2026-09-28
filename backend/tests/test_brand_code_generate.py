"""Server-generated brand codes; unique and tenant isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_brand_generates_code_when_omitted(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    first = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"name": f"Acme {suffix}"},
    )
    assert first.status_code == 200, first.text
    code1 = first.json()["data"]["code"]
    assert code1.startswith("BRD-")
    assert first.json()["data"]["name"] == f"Acme {suffix}"

    second = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"name": f"Beta {suffix}"},
    )
    assert second.status_code == 200, second.text
    code2 = second.json()["data"]["code"]
    assert code2.startswith("BRD-")
    assert code1 != code2

    preserved = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": f"KEEP{suffix[:6]}", "name": f"Keep Brand {suffix}"},
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["data"]["code"] == f"KEEP{suffix[:6]}".upper()


@pytest.mark.asyncio
async def test_create_brand_duplicate_code_409(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    body = {"code": f"UNIQ{suffix[:6]}", "name": f"Unique A {suffix}"}
    ok = await ac.post("/api/v1/catalog/brands", headers=headers, json=body)
    assert ok.status_code == 200, ok.text
    dup = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": f"UNIQ{suffix[:6]}", "name": f"Unique B {suffix}"},
    )
    assert dup.status_code == 409, dup.text


@pytest.mark.asyncio
async def test_create_brand_tenant_isolation(client):
    ac, _seed = client
    alpha = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/catalog/brands",
        headers=alpha,
        json={"name": f"Alpha Brand {suffix}"},
    )
    assert created.status_code == 200, created.text
    brand_id = created.json()["data"]["id"]

    listed_beta = await ac.get("/api/v1/catalog/brands", headers=beta)
    assert listed_beta.status_code in {200, 403}, listed_beta.text
    if listed_beta.status_code == 200:
        assert brand_id not in {r["id"] for r in listed_beta.json()["data"]}

    patched_beta = await ac.patch(
        f"/api/v1/catalog/brands/{brand_id}",
        headers=beta,
        json={"name": "Hijack"},
    )
    assert patched_beta.status_code in {403, 404}, patched_beta.text
