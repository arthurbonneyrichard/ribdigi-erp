"""Multi-level purchase request approval matrix."""

from __future__ import annotations

import pyotp
import pytest
from fastapi import HTTPException

from app import models as m
from app import purchasing as purchasing_svc
from tests.conftest import auth_headers


def test_default_pr_levels_require_manager_then_admin():
    levels = purchasing_svc.default_pr_approval_levels()
    assert len(levels) == 2
    assert "store_manager" in levels[0]["roles"]
    assert "company_admin" in levels[1]["roles"]
    from app.expenses import steps_required_from_matrix

    assert steps_required_from_matrix(0, levels) == 0
    assert steps_required_from_matrix(100, levels) == 1
    assert steps_required_from_matrix(6000, levels) == 2


@pytest.mark.asyncio
async def test_pr_two_level_http_flow(client, db_session):
    ac, seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    super_h = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    # Tighten L1 to store_manager only so admin cannot skip ahead.
    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    await purchasing_svc.update_pr_approval_settings(
        db_session,
        tenant,
        levels=[
            {"min_amount": 0.01, "roles": ["store_manager"], "label": "Store Manager"},
            {"min_amount": 1000, "roles": ["company_admin", "super_admin"], "label": "Admin"},
        ],
    )
    await db_session.commit()

    supplier = await ac.post("/api/v1/suppliers", headers=admin, json={"name": "Matrix Sup"})
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    # Admin creates high-value PR (cannot self-approve L1 as store_manager-only).
    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 200, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    pr_id = created.json()["data"]["id"]
    submitted = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=admin)
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()["data"]
    assert body["status"] == "pending"
    assert body["approval_steps_required"] == 2
    assert body["approval_step"] == 1
    assert body["estimated_total"] == 2000.0

    # Wrong role for L1
    denied = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=admin)
    assert denied.status_code == 403

    mid = await ac.post(
        f"/api/v1/purchasing/requests/{pr_id}/approve",
        headers=mgr,
        json={"comment": "OK L1"},
    )
    assert mid.status_code == 200, mid.text
    assert mid.json()["data"]["status"] == "pending"
    assert mid.json()["data"]["approval_step"] == 2

    # Same actor cannot do L2
    again = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=mgr)
    assert again.status_code == 403

    final = await ac.post(
        f"/api/v1/purchasing/requests/{pr_id}/approve",
        headers=super_h,
        json={"comment": "OK L2"},
    )
    assert final.status_code == 200, final.text
    assert final.json()["data"]["status"] == "approved"
    actions = final.json()["data"]["approval_actions"]
    assert [a["step"] for a in actions if a["action"] == "approve"] == [1, 2]


@pytest.mark.asyncio
async def test_pr_settings_admin_only_and_role_reject(client, db_session):
    ac, seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blocked = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=mgr,
        json={
            "levels": [
                {"min_amount": 1, "roles": ["store_manager"], "label": "L1"},
            ]
        },
    )
    assert blocked.status_code == 403

    ok = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=admin,
        json={
            "levels": [
                {"min_amount": 1, "roles": ["store_manager"], "label": "Manager"},
                {"min_amount": 500, "roles": ["company_admin"], "label": "Admin"},
            ]
        },
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["data"]["levels"]) == 2

    settings = await ac.get("/api/v1/purchasing/settings", headers=mgr)
    assert settings.status_code == 200
    assert settings.json()["data"]["levels"][0]["label"] == "Manager"


@pytest.mark.asyncio
async def test_pr_reject_requires_step_role(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    await purchasing_svc.update_pr_approval_settings(
        db_session,
        tenant,
        levels=[
            {"min_amount": 0.01, "roles": ["store_manager"], "label": "Manager"},
        ],
    )
    supplier = m.Party(tenant_id=tenant_id, kind="supplier", name="Svc Sup", credit_limit=0)
    db_session.add(supplier)
    await db_session.flush()
    pr = await purchasing_svc.create_purchase_request(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seeded["p1"].id, "quantity": 2, "unit_price": 5}],
    )
    await purchasing_svc.submit_purchase_request(
        db_session, tenant_id=tenant_id, user_id=seeded["admin1"].id, request_id=pr.id
    )
    with pytest.raises(HTTPException) as denied:
        await purchasing_svc.reject_purchase_request(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["admin1"].id,
            request_id=pr.id,
            reason="No",
            actor_role="company_admin",
        )
    assert denied.value.status_code == 403

    rejected = await purchasing_svc.reject_purchase_request(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        request_id=pr.id,
        reason="Budget",
        actor_role="store_manager",
    )
    await db_session.commit()
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "Budget"
