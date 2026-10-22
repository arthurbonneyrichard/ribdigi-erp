"""Add Customer: auth ownership, optional group, no partial save, tenant isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from app import customers as customers_svc
from app import schema_compat
from app.http_errors import _missing_related_detail
from sqlalchemy import text
from tests.conftest import auth_headers


def _names(payload) -> set[str]:
    return {row["name"] for row in payload.json()["data"]}


async def _count_named(ac, headers, name: str) -> int:
    r = await ac.get("/api/v1/customers", headers=headers)
    assert r.status_code == 200, r.text
    return sum(1 for row in r.json()["data"] if row["name"] == name)


@pytest.mark.asyncio
async def test_create_customer_with_valid_group(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    groups = await ac.get("/api/v1/customers/groups", headers=headers)
    assert groups.status_code == 200, groups.text
    group = next(g for g in groups.json()["data"] if g["code"] == "RETAIL")
    r = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Ada Mensah", "customer_group_id": group["id"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["name"] == "Ada Mensah"
    assert body["tenant_id"] == seed["t1"].id
    assert body["customer_group_id"] == group["id"]
    listed = await ac.get("/api/v1/customers", headers=headers)
    assert "Ada Mensah" in _names(listed)


@pytest.mark.asyncio
async def test_create_customer_optional_group_empty(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Walk-in Kofi", "customer_group_id": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["customer_group_id"] is None
    assert r.json()["data"]["customer_group"] is None


@pytest.mark.asyncio
async def test_create_customer_rejects_unknown_group_without_partial_row(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    name = "Ghost Group Customer"
    before = await _count_named(ac, headers, name)
    missing = str(uuid4())
    r = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": name, "customer_group_id": missing},
    )
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"][-1] == "customer_group"
    assert "customer group" in detail[0]["msg"].lower()
    assert "required related record is missing" not in r.text.lower()
    assert await _count_named(ac, headers, name) == before


@pytest.mark.asyncio
async def test_create_customer_rejects_other_tenant_group(client):
    ac, _seed = client
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    groups = await ac.get("/api/v1/customers/groups", headers=beta)
    assert groups.status_code == 200, groups.text
    foreign = groups.json()["data"][0]["id"]
    alpha = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    name = "Cross Tenant Group"
    before = await _count_named(ac, alpha, name)
    r = await ac.post(
        "/api/v1/customers",
        headers=alpha,
        json={"name": name, "customer_group_id": foreign},
    )
    assert r.status_code == 404, r.text
    assert await _count_named(ac, alpha, name) == before


@pytest.mark.asyncio
async def test_create_customer_rejects_browser_tenant_and_company_ids(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Injected Tenant", "tenant_id": seed["t2"].id},
    )
    assert r.status_code == 422, r.text
    r2 = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Injected Company", "company_id": str(uuid4())},
    )
    assert r2.status_code == 422, r2.text


@pytest.mark.asyncio
async def test_saved_customer_on_company_list_hidden_from_other_tenant(client, db_session):
    ac, seed = client
    schema_compat.clear_column_cache()
    await db_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id VARCHAR(36) PRIMARY KEY,
                tenant_id VARCHAR(36) NOT NULL,
                code VARCHAR(40) NOT NULL,
                name VARCHAR(200) NOT NULL
            )
            """
        )
    )
    await db_session.execute(text("ALTER TABLE parties ADD COLUMN company_id VARCHAR(36)"))
    company_id = str(uuid4())
    await db_session.execute(
        text(
            "INSERT INTO companies (id, tenant_id, code, name) VALUES (:id, :tid, 'MAIN', 'Alpha Co')"
        ),
        {"id": company_id, "tid": seed["t1"].id},
    )
    await db_session.commit()
    schema_compat.clear_column_cache()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Company Ada"},
    )
    assert r.status_code == 200, r.text
    created = r.json()["data"]
    assert created["company_id"] == company_id
    assert created["tenant_id"] == seed["t1"].id

    live = await schema_compat.fetch_live_dicts(
        db_session, "parties", "id = :id", {"id": created["id"]}
    )
    assert live and live[0]["company_id"] == company_id
    assert live[0]["tenant_id"] == seed["t1"].id

    listed = await ac.get("/api/v1/customers", headers=headers)
    assert listed.status_code == 200, listed.text
    names = _names(listed)
    assert "Company Ada" in names
    ids = {row["id"] for row in listed.json()["data"]}
    assert created["id"] in ids

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    other = await ac.get("/api/v1/customers", headers=beta)
    assert other.status_code == 200, other.text
    assert "Company Ada" not in _names(other)
    other_ids = {row["id"] for row in other.json()["data"]}
    assert created["id"] not in other_ids


@pytest.mark.asyncio
async def test_required_company_missing_does_not_create(client, db_session, monkeypatch):
    ac, _seed = client
    schema_compat.clear_column_cache()
    await db_session.execute(text("ALTER TABLE parties ADD COLUMN company_id VARCHAR(36)"))
    await db_session.commit()
    schema_compat.clear_column_cache()
    monkeypatch.setattr("app.customers.live_column_nullable", AsyncMock(return_value=False))

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    name = "No Company Customer"
    before = await _count_named(ac, headers, name)
    r = await ac.post("/api/v1/customers", headers=headers, json={"name": name})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"][-1] == "company"
    assert "company is required" in detail[0]["msg"].lower()
    assert "required related record is missing" not in r.text.lower()
    assert await _count_named(ac, headers, name) == before


def test_integrity_mapper_uses_field_messages():
    class _Orig:
        def __init__(self, msg: str):
            self.msg = msg

        def __str__(self):
            return self.msg

    class _Exc:
        def __init__(self, msg: str):
            self.orig = _Orig(msg)

    mapped = customers_svc.map_party_integrity_error(_Exc('null value in column "company_id"'))  # type: ignore[arg-type]
    assert mapped.status_code == 400
    assert mapped.detail[0]["loc"][-1] == "company"

    mapped_g = customers_svc.map_party_integrity_error(_Exc("fk_parties_customer_group_id"))  # type: ignore[arg-type]
    assert mapped_g.detail[0]["loc"][-1] == "customer_group"

    detail = _missing_related_detail('null value in column "company_id"', "/api/v1/customers")
    assert detail[0]["loc"][-1] == "company"
    generic = _missing_related_detail("foreign key constraint failed", "/api/v1/customers")
    assert "customer" in generic.lower()
    assert "required related record is missing" not in generic.lower()
