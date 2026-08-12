"""Record-level RBAC scope (own vs all)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.expenses import create_expense, ensure_default_categories
from app.rbac import (
    RECORD_SCOPE_KEY,
    assert_record_access,
    permissions_for_role,
    record_scope_for_claims,
    record_scope_from_permissions,
)
from app.security import hash_password
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_user(db_session, seed, *, email: str, role: str, record_scope: str | None = None):
    perms = permissions_for_role(role)
    if record_scope is not None:
        perms = {**perms, RECORD_SCOPE_KEY: record_scope}
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name=email.split("@")[0],
        password_hash=hash_password("SecurePass123!"),
        role=role,
        email_verified=True,
        permissions=perms,
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_record_scope_defaults_and_override():
    assert record_scope_from_permissions("cashier", None) == "own"
    assert record_scope_from_permissions("store_manager", None) == "all"
    assert record_scope_from_permissions("cashier", {RECORD_SCOPE_KEY: "all"}) == "all"
    assert record_scope_for_claims({"role": "sales_officer", "permissions": {}}) == "own"


def test_assert_record_access_own_hides_foreign():
    claims = {"role": "cashier", "sub": "u1", "permissions": {RECORD_SCOPE_KEY: "own"}}
    assert_record_access(claims, "u1")
    with pytest.raises(Exception) as exc:
        assert_record_access(claims, "u2")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_expense_own_scope_hides_others_records(client, db_session):
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    await ensure_default_categories(db_session, seed["t1"].id)
    await db_session.commit()

    foreign = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        amount=40,
        description="Admin expense",
        category="Utilities",
        payment_method="cash",
    )
    await db_session.commit()

    # Restrict store manager to own records
    patched = await ac.patch(
        f"/api/v1/users/{seed['mgr1'].id}",
        headers=admin,
        json={"record_scope": "own"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["record_scope"] == "own"

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    missing = await ac.get(f"/api/v1/expenses/{foreign.id}", headers=mgr)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/expenses", headers=mgr)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["data"]}
    assert foreign.id not in ids

    created = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={"amount": 12, "description": "Mine", "category": "Supplies", "payment_method": "cash"},
    )
    assert created.status_code == 200, created.text
    mine_id = created.json()["data"]["id"]
    ok = await ac.get(f"/api/v1/expenses/{mine_id}", headers=mgr)
    assert ok.status_code == 200

    # Admin with default all still sees foreign expense
    admin2 = await _admin_headers(ac, seed)
    still = await ac.get(f"/api/v1/expenses/{foreign.id}", headers=admin2)
    assert still.status_code == 200


@pytest.mark.asyncio
async def test_roles_catalog_includes_record_scope(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/roles", headers=headers)
    assert r.status_code == 200
    by_role = {row["role"]: row for row in r.json()["data"]}
    assert by_role["cashier"]["record_scope"] == "own"
    assert by_role["accountant"]["record_scope"] == "all"


@pytest.mark.asyncio
async def test_sales_docs_own_scope_hides_peers(client, db_session):
    ac, seed = client
    await _seed_user(db_session, seed, email="so1@alpha.example.com", role="sales_officer")
    await _seed_user(db_session, seed, email="so2@alpha.example.com", role="sales_officer")
    so1 = await auth_headers(ac, email="so1@alpha.example.com", tenant_slug="alpha")
    so2 = await auth_headers(ac, email="so2@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}

    foreign_q = await ac.post(
        "/api/v1/sales/quotations",
        headers=so1,
        json={"customer_id": seed["party1"].id, "items": [item]},
    )
    assert foreign_q.status_code == 200, foreign_q.text
    q_id = foreign_q.json()["data"]["id"]

    foreign_o = await ac.post(
        "/api/v1/sales/orders",
        headers=so1,
        json={"customer_id": seed["party1"].id, "items": [item]},
    )
    assert foreign_o.status_code == 200, foreign_o.text
    o_id = foreign_o.json()["data"]["id"]

    assert (await ac.get(f"/api/v1/sales/quotations/{q_id}", headers=so2)).status_code == 404
    assert (await ac.get(f"/api/v1/sales/orders/{o_id}", headers=so2)).status_code == 404
    assert (await ac.post(f"/api/v1/sales/quotations/{q_id}/send", headers=so2)).status_code == 404
    assert (await ac.post(f"/api/v1/sales/orders/{o_id}/confirm", headers=so2)).status_code == 404

    q_list = await ac.get("/api/v1/sales/quotations", headers=so2)
    assert q_list.status_code == 200
    assert q_id not in {row["id"] for row in q_list.json()["data"]}

    o_list = await ac.get("/api/v1/sales/orders", headers=so2)
    assert o_list.status_code == 200
    assert o_id not in {row["id"] for row in o_list.json()["data"]}

    mine = await ac.post(
        "/api/v1/sales/quotations",
        headers=so2,
        json={"customer_id": seed["party1"].id, "items": [item]},
    )
    assert mine.status_code == 200, mine.text
    mine_id = mine.json()["data"]["id"]
    assert (await ac.get(f"/api/v1/sales/quotations/{mine_id}", headers=so2)).status_code == 200


@pytest.mark.asyncio
async def test_purchasing_own_scope_and_approve_bypass(client, db_session):
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    await _seed_user(
        db_session, seed, email="io1@alpha.example.com", role="inventory_officer", record_scope="own"
    )
    await _seed_user(
        db_session, seed, email="io2@alpha.example.com", role="inventory_officer", record_scope="own"
    )
    io1 = await auth_headers(ac, email="io1@alpha.example.com", tenant_slug="alpha")
    io2 = await auth_headers(ac, email="io2@alpha.example.com", tenant_slug="alpha")
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Scope Supplier", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    foreign_pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=io1,
        json={
            "preferred_supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 3}],
        },
    )
    assert foreign_pr.status_code == 200, foreign_pr.text
    pr_id = foreign_pr.json()["data"]["id"]

    assert (await ac.get(f"/api/v1/purchasing/requests/{pr_id}", headers=io2)).status_code == 404
    listed = await ac.get("/api/v1/purchasing/requests", headers=io2)
    assert listed.status_code == 200
    assert pr_id not in {row["id"] for row in listed.json()["data"]}

    # Creator can submit; peer cannot
    assert (await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=io2)).status_code == 404
    submitted = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=io1)
    assert submitted.status_code == 200, submitted.text

    # Approver with all-scope still sees/approves (bypass own-scope)
    approved = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=mgr)
    assert approved.status_code == 200, approved.text

    foreign_po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io1,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 1}],
        },
    )
    assert foreign_po.status_code == 200, foreign_po.text
    po_id = foreign_po.json()["data"]["id"]
    assert (await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=io2)).status_code == 404
    assert (await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io2)).status_code == 404

    foreign_inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=io1,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert foreign_inv.status_code == 200, foreign_inv.text
    inv_id = foreign_inv.json()["data"]["id"]
    assert (await ac.get(f"/api/v1/purchasing/invoices/{inv_id}", headers=io2)).status_code == 404
    # Approval bypass: peer with write + own scope can still approve (no assert on approve)
    approve_peer = await ac.post(f"/api/v1/purchasing/invoices/{inv_id}/approve", headers=io2)
    assert approve_peer.status_code == 200, approve_peer.text
