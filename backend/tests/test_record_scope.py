"""Record-level RBAC scope (own vs all)."""

from __future__ import annotations

import pyotp
import pytest

from app.expenses import create_expense, ensure_default_categories
from app.rbac import (
    RECORD_SCOPE_KEY,
    assert_record_access,
    record_scope_for_claims,
    record_scope_from_permissions,
)
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


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
