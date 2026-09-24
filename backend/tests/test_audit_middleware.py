"""HTTP mutation audit middleware auto-coverage (BR-17.1 / G19)."""

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
    assert module_from_path("/api/v1/branches") == "company"
    entity, eid = entity_from_path(
        "/api/v1/products/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )
    assert eid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert entity == "products"


@pytest.mark.asyncio
async def test_mutating_request_writes_http_write_audit(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    before = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
            )
        )
    ).scalars().all()
    before_ids = {r.id for r in before}

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Audit Widget",
            "sku": "AUD-WIDGET-1",
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 5,
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

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
    hit = next(
        (
            r
            for r in new_rows
            if r.details
            and r.details.get("path") == "/api/v1/products"
            and r.details.get("method") == "POST"
        ),
        new_rows[-1],
    )
    assert hit.module == "inventory"
    assert hit.details.get("source") == "audit_middleware"
    assert hit.integrity_hash
    assert hit.user_id

    # Domain write + middleware write must keep chain valid.
    verify = await ac.get("/api/v1/audit-logs/verify", headers=headers)
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["valid"] is True

    # Product id was returned; ensure we actually created something.
    assert product_id


@pytest.mark.asyncio
async def test_failed_mutation_not_audited_by_middleware(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    missing = await ac.patch(
        "/api/v1/stores/00000000-0000-0000-0000-000000000099/drawer",
        headers=headers,
        json={"drawer_mode": "mock"},
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
    failed_paths = [
        r
        for r in after
        if (r.details or {}).get("path", "").endswith("00000000-0000-0000-0000-000000000099/drawer")
    ]
    assert not failed_paths


@pytest.mark.asyncio
async def test_middleware_disabled_skips_http_write(client, db_session, monkeypatch):
    monkeypatch.setattr("app.audit_middleware.settings.AUDIT_HTTP_MIDDLEWARE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.AUDIT_HTTP_MIDDLEWARE_ENABLED", False)
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    before = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
                m.AuditLog.module == "expenses",
            )
        )
    ).scalars().all()
    before_ids = {r.id for r in before}

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Supplies",
            "amount": 3,
            "description": "No middleware audit",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text

    after = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "http_write",
                m.AuditLog.module == "expenses",
            )
        )
    ).scalars().all()
    new_rows = [r for r in after if r.id not in before_ids]
    assert not new_rows
