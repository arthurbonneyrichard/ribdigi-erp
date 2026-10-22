"""Server-generated unit codes; unique, base parent, and tenant isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_create_unit_generates_code_when_omitted(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    first = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"name": f"Crate {suffix}"},
    )
    assert first.status_code == 200, first.text
    code1 = first.json()["data"]["code"]
    assert code1.startswith("UNT-")
    assert first.json()["data"]["name"] == f"Crate {suffix}"

    second = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"name": f"Pallet {suffix}"},
    )
    assert second.status_code == 200, second.text
    code2 = second.json()["data"]["code"]
    assert code2.startswith("UNT-")
    assert code1 != code2

    preserved = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": f"K{suffix[:6]}", "name": f"Keep Unit {suffix}"},
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["data"]["code"] == f"K{suffix[:6]}".upper()


@pytest.mark.asyncio
async def test_create_unit_duplicate_code_409(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    body = {"code": f"U{suffix[:6]}", "name": f"Unique A {suffix}"}
    ok = await ac.post("/api/v1/catalog/units", headers=headers, json=body)
    assert ok.status_code == 200, ok.text
    dup = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": f"U{suffix[:6]}", "name": f"Unique B {suffix}"},
    )
    assert dup.status_code == 409, dup.text


@pytest.mark.asyncio
async def test_create_unit_invalid_base_and_tenant_isolation(client):
    ac, _seed = client
    alpha = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/catalog/units",
        headers=alpha,
        json={"name": f"Alpha Unit {suffix}"},
    )
    assert created.status_code == 200, created.text
    unit_id = created.json()["data"]["id"]

    missing = await ac.post(
        "/api/v1/catalog/units",
        headers=alpha,
        json={"name": f"Bad Base {suffix}", "base_unit_id": str(uuid4())},
    )
    assert missing.status_code == 404, missing.text

    listed_beta = await ac.get("/api/v1/catalog/units", headers=beta)
    assert listed_beta.status_code in {200, 403}, listed_beta.text
    if listed_beta.status_code == 200:
        assert unit_id not in {r["id"] for r in listed_beta.json()["data"]}

    patched_beta = await ac.patch(
        f"/api/v1/catalog/units/{unit_id}",
        headers=beta,
        json={"name": "Hijack"},
    )
    assert patched_beta.status_code in {403, 404}, patched_beta.text

    child_on_foreign = await ac.post(
        "/api/v1/catalog/units",
        headers=beta,
        json={"name": f"Beta Child {suffix}", "base_unit_id": unit_id},
    )
    assert child_on_foreign.status_code in {403, 404}, child_on_foreign.text
