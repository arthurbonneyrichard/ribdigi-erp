"""Purge must clear nullable FKs and survive SQLite FK enforcement (Postgres shape)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import event, text

from tests.conftest import auth_headers, platform_owner_headers


@pytest.fixture
def _sqlite_fk_on(db_engine):
    """Match Postgres: reject deletes that leave dangling FKs."""

    @event.listens_for(db_engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return db_engine


async def _owner(ac, seed):
    return await platform_owner_headers(ac, seed)


@pytest.mark.asyncio
async def test_owner_purge_with_fk_enforcement(client, seeded, db_engine, _sqlite_fk_on):
    ac, seed = client
    # Re-enable FK on the shared engine connection used by the app.
    async with db_engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))

    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    slug = f"fk-del-{suffix}"
    email = f"fk-{suffix}@deleteco.example.com"
    created = await ac.post(
        "/api/v1/tenants",
        headers=owner,
        json={
            "company_name": f"FK Delete Co {suffix}",
            "slug": slug,
            "admin_email": email,
            "admin_password": "SecurePass123!",
            "industry": "retail",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    verified = await ac.post(f"/api/v1/tenants/{slug}/verify-admin", headers=owner)
    assert verified.status_code == 200, verified.text
    tenant_headers = await auth_headers(ac, email=email, tenant_slug=slug)

    me = await ac.get("/api/v1/me", headers=tenant_headers)
    admin_id = me.json()["data"]["id"]

    branch = await ac.post(
        "/api/v1/branches",
        headers=tenant_headers,
        json={
            "name": f"HQ {suffix}",
            "code": f"HQ{suffix[:6].upper()}",
            "manager_id": admin_id,
        },
    )
    assert branch.status_code == 200, branch.text
    branch_id = branch.json()["data"]["id"]

    assigned = await ac.patch(
        f"/api/v1/users/{admin_id}",
        headers=tenant_headers,
        json={"branch_id": branch_id},
    )
    assert assigned.status_code == 200, assigned.text

    stores = await ac.get("/api/v1/stores", headers=tenant_headers)
    store_id = stores.json()["data"][0]["id"]
    store_patch = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=tenant_headers,
        json={"manager_id": admin_id},
    )
    assert store_patch.status_code == 200, store_patch.text

    product = await ac.post(
        "/api/v1/products",
        headers=tenant_headers,
        json={"name": f"FK item {suffix}", "selling_price": 10, "cost_price": 4},
    )
    assert product.status_code == 200, product.text

    # Manual journal creates accounts lines that used to block naive deletes.
    accounts = await ac.get("/api/v1/accounting/accounts", headers=tenant_headers)
    assert accounts.status_code == 200, accounts.text
    cash = next(
        (row for row in accounts.json()["data"] if row.get("code") == "1000"),
        accounts.json()["data"][0],
    )
    equity = next(
        (row for row in accounts.json()["data"] if str(row.get("account_type") or "").lower() == "equity"),
        None,
    )
    if equity is None:
        equity = next(
            (row for row in accounts.json()["data"] if row["id"] != cash["id"]),
            cash,
        )
    journal = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=tenant_headers,
        json={
            "description": f"Purge journal {suffix}",
            "lines": [
                {"account_id": cash["id"], "debit": 5, "credit": 0},
                {"account_id": equity["id"], "debit": 0, "credit": 5},
            ],
        },
    )
    assert journal.status_code == 200, journal.text

    # Expense + customer create more account/party FKs that block naive deletes.
    expense = await ac.post(
        "/api/v1/expenses",
        headers=tenant_headers,
        json={
            "category": "Office",
            "description": f"Purge expense {suffix}",
            "amount": 12.5,
            "payment_method": "cash",
            "liquid_account_id": cash["id"],
        },
    )
    assert expense.status_code == 200, expense.text

    customer = await ac.post(
        "/api/v1/customers",
        headers=tenant_headers,
        json={"name": f"Purge Cust {suffix}", "email": f"cust-{suffix}@example.com"},
    )
    assert customer.status_code == 200, customer.text

    deleted = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=owner,
        json={"confirm_slug": slug},
    )
    assert deleted.status_code == 200, deleted.text

    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert slug not in {row["slug"] for row in listed.json()["data"]}
