"""Purchase request multi-level approval matrix (BR-6.2)."""

from __future__ import annotations

import pyotp
import pytest
from fastapi import HTTPException

from app import purchase_requests as pr_svc
from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers


def test_normalize_default_is_two_levels():
    levels = pr_svc.default_approval_levels()
    assert len(levels) == 2
    assert levels[0]["roles"] == ["store_manager"]
    assert "company_admin" in levels[1]["roles"]


def test_normalize_rejects_unknown_role():
    with pytest.raises(HTTPException) as exc:
        pr_svc.normalize_approval_matrix(
            {"levels": [{"roles": ["not_a_role"], "label": "Bad"}]}
        )
    assert exc.value.status_code == 400


async def _super(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seeded):
    user = m.User(
        tenant_id=seeded["t1"].id,
        email="io-pr-matrix@alpha.example.com",
        full_name="IO PR Matrix",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_pr_settings_patch_and_single_level(client, db_session):
    ac, seeded = client
    await _seed_io(db_session, seeded)
    io = await auth_headers(ac, email="io-pr-matrix@alpha.example.com", tenant_slug="alpha")
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    admin = await _super(ac, seeded)

    got = await ac.get("/api/v1/purchasing/requests/settings", headers=mgr)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["steps_required"] == 2

    patched = await ac.patch(
        "/api/v1/purchasing/requests/settings",
        headers=admin,
        json={
            "levels": [
                {
                    "roles": ["store_manager", "company_admin", "super_admin"],
                    "label": "Single Approver",
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["steps_required"] == 1

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=io,
        json={"items": [{"product_id": seeded["p1"].id, "quantity": 2}]},
    )
    rid = created.json()["data"]["id"]
    await ac.post(f"/api/v1/purchasing/requests/{rid}/submit", headers=io, json={})
    approved = await ac.post(f"/api/v1/purchasing/requests/{rid}/approve", headers=mgr, json={})
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["approval_steps_required"] == 1


@pytest.mark.asyncio
async def test_pr_wrong_role_for_level(db_session, seeded):
    tenant_id = seeded["t1"].id
    io = m.User(
        tenant_id=tenant_id,
        email="io-pr-role@alpha.example.com",
        full_name="IO PR Role",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(io)
    await db_session.commit()

    pr = await pr_svc.create_request(
        db_session,
        tenant_id=tenant_id,
        user_id=io.id,
        items=[{"product_id": seeded["p1"].id, "quantity": 1}],
    )
    await pr_svc.submit_request(
        db_session, tenant_id=tenant_id, user_id=io.id, request_id=pr.id
    )

    with pytest.raises(HTTPException) as denied:
        await pr_svc.approve_request(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["admin1"].id,
            request_id=pr.id,
            actor_role="company_admin",
        )
    assert denied.value.status_code == 403
    assert "Level-1" in str(denied.value.detail)

    mid = await pr_svc.approve_request(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        request_id=pr.id,
        actor_role="store_manager",
    )
    assert mid.status == "pending"
    assert mid.approval_step == 2

    final = await pr_svc.approve_request(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        request_id=pr.id,
        actor_role="company_admin",
    )
    await db_session.commit()
    assert final.status == "approved"