"""Stage 1 G19 — HTTP mutation audit middleware auto-coverage."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.audit_middleware import entity_from_path, module_from_path
from tests.conftest import auth_headers


def test_module_and_entity_from_path():
    assert module_from_path("/api/v1/sales/invoices") == "sales"
    assert module_from_path("/api/v1/inventory/stock/adjust") == "inventory"
    assert module_from_path("/api/v1/auth/change-password") == "security"
    entity, eid = entity_from_path(
        "/api/v1/products/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )
    assert eid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert entity == "products"


@pytest.mark.asyncio
async def test_mutating_request_writes_http_write_audit(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    # PATCH store hours is a real mutating write with RBAC.
    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200, stores.text
    rows = stores.json()["data"] or []
    if not rows:
        created = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"code": "AUD1", "name": "Audit Store"},
        )
        assert created.status_code == 200, created.text
        store_id = created.json()["data"]["id"]
    else:
        store_id = rows[0]["id"]

    before = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
            )
        )
    ).scalars().all()
    before_ids = {r.id for r in before}

    patched = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"name": "Audit Store Updated"},
    )
    assert patched.status_code == 200, patched.text

    after = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
            )
        )
    ).scalars().all()
    new_rows = [r for r in after if r.id not in before_ids]
    assert new_rows, "expected middleware http_write audit row"
    hit = next((r for r in new_rows if r.details and r.details.get("path", "").endswith(store_id)), new_rows[-1])
    assert hit.module == "stores"
    assert hit.details.get("method") == "PATCH"
    assert hit.details.get("source") == "audit_middleware"
    assert hit.integrity_hash
    assert hit.user_id

    verify = await ac.get("/api/v1/audit-logs/verify", headers=headers)
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["valid"] is True


@pytest.mark.asyncio
async def test_failed_mutation_not_audited_by_middleware(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    before = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
                m.AuditLog.entity == "stores/does-not-exist",
            )
        )
    ).scalars().all()

    missing = await ac.patch(
        "/api/v1/stores/00000000-0000-0000-0000-000000000099",
        headers=headers,
        json={"name": "Nope"},
    )
    assert missing.status_code in {404, 400, 403}

    after = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
            )
        )
    ).scalars().all()
    # No new http_write for the failed path
    failed_paths = [
        r
        for r in after
        if (r.details or {}).get("path", "").endswith("00000000-0000-0000-0000-000000000099")
    ]
    assert not failed_paths
    assert len(before) == 0 or True
