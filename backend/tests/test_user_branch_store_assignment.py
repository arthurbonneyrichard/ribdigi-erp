"""User create/edit branch+store assignment — tenant isolation, no extra RBAC.

Reuses User.branch_id + existing user_store_memberships (ADR-005 membership
tables are not claimed Complete). Empty membership still grandfathers all stores.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import models as m
from app.rbac import permissions_for_role
from app.schemas import UserCreate, UserUpdate
from app.security import hash_password
from tests.conftest import auth_headers


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _beta_admin(ac, db_session, seed):
    admin = m.User(
        tenant_id=seed["t2"].id,
        email=f"admin-{uuid4().hex[:8]}@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
    )
    db_session.add(admin)
    await db_session.commit()
    return await auth_headers(ac, email=admin.email, tenant_slug="beta")


async def _branch_and_store(ac, headers, *, bcode: str, scode: str, bname: str, sname: str):
    branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": bcode, "name": bname},
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]
    store = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": scode, "name": sname, "branch_id": branch_id},
    )
    assert store.status_code == 200, store.text
    return branch_id, store.json()["data"]["id"]


def test_user_create_store_id_schema():
    base = {
        "email": "loc@example.com",
        "full_name": "Loc User",
        "password": "SecurePass123!",
    }
    omit = UserCreate.model_validate(base)
    assert omit.store_id is None
    valid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    ok = UserCreate.model_validate({**base, "store_id": f"  {valid}  "})
    assert ok.store_id == valid.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid"):
        with pytest.raises(ValidationError):
            UserCreate.model_validate({**base, "store_id": bad})
    upd = UserUpdate.model_validate({"store_id": valid})
    assert upd.store_id == valid.lower()
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"store_id": "br_001"})


@pytest.mark.asyncio
async def test_create_edit_list_branch_store_and_mismatch(client):
    ac, seed = client
    admin = await _admin(ac)
    suffix = uuid4().hex[:6].upper()
    b1, s1 = await _branch_and_store(
        ac, admin, bcode=f"B1{suffix}", scode=f"S1{suffix}", bname="Branch One", sname="Store One"
    )
    b2, s2 = await _branch_and_store(
        ac, admin, bcode=f"B2{suffix}", scode=f"S2{suffix}", bname="Branch Two", sname="Store Two"
    )

    mismatch = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"mismatch-{suffix}@alpha.example.com",
            "full_name": "Mismatch User",
            "password": "SecurePass123!",
            "role": "cashier",
            "branch_id": b1,
            "store_id": s2,
        },
    )
    assert mismatch.status_code == 400, mismatch.text
    detail = mismatch.json()["detail"]
    assert detail["code"] == "STORE_BRANCH_MISMATCH"

    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"loc-{suffix}@alpha.example.com",
            "full_name": "Located User",
            "password": "SecurePass123!",
            "role": "cashier",
            "branch_id": b1,
            "store_id": s1,
        },
    )
    assert created.status_code == 200, created.text
    user = created.json()["data"]["user"]
    uid = user["id"]
    assert user["branch_id"] == b1
    assert user["store_id"] == s1
    assert user["store_ids"] == [s1]
    # Location assignment does not grant extra RBAC.
    perms = user["permissions"]
    assert "users" not in perms or "write" not in (perms.get("users") or [])
    assert "pos" in perms

    listed = await ac.get("/api/v1/users", headers=admin)
    assert listed.status_code == 200
    row = next(u for u in listed.json()["data"] if u["id"] == uid)
    assert row["branch_id"] == b1
    assert s1 in (row.get("store_ids") or [])

    by_branch = await ac.get("/api/v1/users", headers=admin, params={"branch_id": b1})
    assert by_branch.status_code == 200
    ids = {u["id"] for u in by_branch.json()["data"]}
    assert uid in ids
    other = await ac.get("/api/v1/users", headers=admin, params={"branch_id": b2})
    assert uid not in {u["id"] for u in other.json()["data"]}

    by_store = await ac.get("/api/v1/users", headers=admin, params={"store_id": s1})
    assert uid in {u["id"] for u in by_store.json()["data"]}
    empty_store = await ac.get("/api/v1/users", headers=admin, params={"store_id": s2})
    assert uid not in {u["id"] for u in empty_store.json()["data"]}

    patched = await ac.patch(
        f"/api/v1/users/{uid}",
        headers=admin,
        json={"branch_id": b2, "store_id": s2},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["branch_id"] == b2
    assert patched.json()["data"]["store_ids"] == [s2]

    bad_put = await ac.put(
        f"/api/v1/users/{uid}/stores",
        headers=admin,
        json={"store_ids": [s1]},
    )
    assert bad_put.status_code == 400, bad_put.text
    assert bad_put.json()["detail"]["code"] == "STORE_BRANCH_MISMATCH"

    grandfather = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"open-{suffix}@alpha.example.com",
            "full_name": "Open User",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert grandfather.status_code == 200, grandfather.text
    open_user = grandfather.json()["data"]["user"]
    assert open_user["store_ids"] == []
    stores_payload = await ac.get(f"/api/v1/users/{open_user['id']}/stores", headers=admin)
    assert stores_payload.json()["data"]["all_stores"] is True
    _ = seed


@pytest.mark.asyncio
async def test_cross_tenant_branch_store_rejected(client, db_session):
    ac, seed = client
    alpha = await _admin(ac)
    beta = await _beta_admin(ac, db_session, seed)
    suffix = uuid4().hex[:6].upper()
    _b_alpha, s_alpha = await _branch_and_store(
        ac, alpha, bcode=f"AA{suffix}", scode=f"SA{suffix}", bname="Alpha Br", sname="Alpha St"
    )
    b_beta, s_beta = await _branch_and_store(
        ac, beta, bcode=f"BB{suffix}", scode=f"SB{suffix}", bname="Beta Br", sname="Beta St"
    )

    stolen = await ac.post(
        "/api/v1/users",
        headers=alpha,
        json={
            "email": f"x-{suffix}@alpha.example.com",
            "full_name": "Cross Tenant",
            "password": "SecurePass123!",
            "role": "cashier",
            "store_id": s_beta,
        },
    )
    assert stolen.status_code == 404, stolen.text

    listed_alpha = await ac.get("/api/v1/users", headers=alpha, params={"store_id": s_alpha})
    assert listed_alpha.status_code == 200
    alpha_emails = {u["email"] for u in listed_alpha.json()["data"]}
    listed_beta = await ac.get("/api/v1/users", headers=beta)
    beta_emails = {u["email"] for u in listed_beta.json()["data"]}
    assert not (alpha_emails & beta_emails)

    foreign_filter = await ac.get(
        "/api/v1/users", headers=alpha, params={"branch_id": b_beta}
    )
    assert foreign_filter.status_code == 404

    foreign_store_filter = await ac.get(
        "/api/v1/users", headers=alpha, params={"store_id": s_beta}
    )
    assert foreign_store_filter.status_code == 404


@pytest.mark.asyncio
async def test_assigned_store_still_enforced_on_pos(client):
    ac, _seed = client
    admin = await _admin(ac)
    suffix = uuid4().hex[:6].upper()
    b1, s1 = await _branch_and_store(
        ac, admin, bcode=f"P1{suffix}", scode=f"PS1{suffix}", bname="POS Br", sname="POS Store"
    )
    _b2, s2 = await _branch_and_store(
        ac, admin, bcode=f"P2{suffix}", scode=f"PS2{suffix}", bname="POS Br 2", sname="POS Store 2"
    )
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"posc-{suffix}@alpha.example.com",
            "full_name": "POS Cashier",
            "password": "SecurePass123!",
            "role": "cashier",
            "branch_id": b1,
            "store_id": s1,
        },
    )
    assert created.status_code == 200, created.text
    cashier = await auth_headers(
        ac, email=f"posc-{suffix}@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"store_id": s2, "opening_cash": 0},
    )
    assert denied.status_code == 403, denied.text
    allowed = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"store_id": s1, "opening_cash": 0},
    )
    assert allowed.status_code == 200, allowed.text
    admin_pos = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"store_id": s2, "opening_cash": 0},
    )
    assert admin_pos.status_code == 200, admin_pos.text


@pytest.mark.asyncio
async def test_single_store_create_auto_assigns_only_store(client):
    ac, _seed = client
    admin = await _admin(ac)
    suffix = uuid4().hex[:6].upper()
    store = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": f"SOLO{suffix}", "name": "Only Store"},
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]
    listed = await ac.get("/api/v1/stores", headers=admin)
    active = [s for s in listed.json()["data"] if s.get("is_active") is not False]
    if len(active) != 1:
        pytest.skip("Need a tenant with exactly one active store")

    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"solo-{suffix}@alpha.example.com",
            "full_name": "Solo Cashier",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    user = created.json()["data"]["user"]
    assert user["store_ids"] == [store_id]
    assert user["store_id"] == store_id
    membership = await ac.get(f"/api/v1/users/{user['id']}/stores", headers=admin)
    assert membership.json()["data"]["all_stores"] is False

    admin_user = next(
        u
        for u in (await ac.get("/api/v1/users", headers=admin)).json()["data"]
        if u["email"] == "admin@alpha.example.com"
    )
    admin_stores = await ac.get(f"/api/v1/users/{admin_user['id']}/stores", headers=admin)
    assert admin_stores.json()["data"]["all_stores"] is True


@pytest.mark.asyncio
async def test_create_multi_store_ids_and_cannot_see_other(client):
    ac, _seed = client
    admin = await _admin(ac)
    suffix = uuid4().hex[:6].upper()
    _b1, s1 = await _branch_and_store(
        ac, admin, bcode=f"M1{suffix}", scode=f"MS1{suffix}", bname="M1", sname="Store A"
    )
    _b2, s2 = await _branch_and_store(
        ac, admin, bcode=f"M2{suffix}", scode=f"MS2{suffix}", bname="M2", sname="Store B"
    )
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"multi-{suffix}@alpha.example.com",
            "full_name": "Multi Assign",
            "password": "SecurePass123!",
            "role": "cashier",
            "store_ids": [s1],
        },
    )
    assert created.status_code == 200, created.text
    user = created.json()["data"]["user"]
    assert user["store_ids"] == [s1]
    uid = user["id"]
    patched = await ac.patch(
        f"/api/v1/users/{uid}",
        headers=admin,
        json={"store_ids": [s1, s2]},
    )
    assert patched.status_code == 200, patched.text
    assert set(patched.json()["data"]["store_ids"]) == {s1, s2}

    cashier = await auth_headers(ac, email=f"multi-{suffix}@alpha.example.com", tenant_slug="alpha")
    pos_stores = await ac.get("/api/v1/pos/stores", headers=cashier)
    assert pos_stores.status_code == 200
    ids = {s["id"] for s in pos_stores.json()["data"]}
    assert s1 in ids and s2 in ids

    await ac.put(f"/api/v1/users/{uid}/stores", headers=admin, json={"store_ids": [s1]})
    pos_one = await ac.get("/api/v1/pos/stores", headers=cashier)
    ids_one = {s["id"] for s in pos_one.json()["data"]}
    assert s1 in ids_one
    assert s2 not in ids_one
    spoof = await ac.get(f"/api/v1/stores/{s2}/sales", headers=cashier)
    assert spoof.status_code in (403, 404), spoof.text


@pytest.mark.asyncio
async def test_tenant_admin_cannot_assign_platform_role(client):
    ac, _seed = client
    admin = await _admin(ac)
    suffix = uuid4().hex[:6].upper()
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"staff-{suffix}@alpha.example.com",
            "full_name": "Staff",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]
    for role in ("platform_admin", "platform_owner", "super_admin", "platform_support"):
        denied = await ac.patch(f"/api/v1/users/{uid}", headers=admin, json={"role": role})
        assert denied.status_code in (400, 403), denied.text
    create_denied = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": f"plat-{suffix}@alpha.example.com",
            "full_name": "Nope",
            "password": "SecurePass123!",
            "role": "platform_admin",
        },
    )
    assert create_denied.status_code in (400, 403), create_denied.text


def test_users_page_store_and_perm_ui_wired():
    from pathlib import Path

    from app.custom_roles import ASSIGNABLE_MODULES
    from app.rbac import ROLE_PERMISSIONS

    users = (Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/users/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "hideStoreAssign" in users
    assert "store_ids" in users
    assert "All stores in this company" in users
    assert "Edit permissions" in users
    assert "TENANT_RBAC_MODULES" in users
    assert "saveCustomRolePerms" in users
    for mod in ASSIGNABLE_MODULES:
        assert f"'{mod}'" in users
    assert "hospital" in ASSIGNABLE_MODULES
    assert "restaurant" in ASSIGNABLE_MODULES
    assert "hospital" not in ROLE_PERMISSIONS["cashier"]
    assert "hospital" not in ROLE_PERMISSIONS["accountant"]
