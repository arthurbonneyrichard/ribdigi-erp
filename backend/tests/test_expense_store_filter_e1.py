"""Expense report store_id filter (BR-14.4 / BR-14.5)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expense_reports_filter_by_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    admin = seed["admin1"]

    branch = m.Branch(tenant_id=tenant_id, code="HQ", name="Head Office", is_active=True)
    other_branch = m.Branch(tenant_id=tenant_id, code="EAST", name="East", is_active=True)
    db_session.add_all([branch, other_branch])
    await db_session.flush()

    store_a = m.Store(
        tenant_id=tenant_id,
        code="A1",
        name="Store A",
        branch_id=branch.id,
        is_active=True,
    )
    store_b = m.Store(
        tenant_id=tenant_id,
        code="B1",
        name="Store B",
        branch_id=other_branch.id,
        is_active=True,
    )
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    listed = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert listed.status_code == 200
    cat_id = listed.json()["data"][0]["id"]
    cat_name = listed.json()["data"][0]["name"]

    now = datetime.utcnow()
    db_session.add_all(
        [
            m.Expense(
                tenant_id=tenant_id,
                category_id=cat_id,
                category=cat_name,
                description="Store A spend",
                amount=55,
                expense_date=now,
                payment_method="cash",
                status="approved",
                created_by=admin.id,
                approved_by=admin.id,
                approved_at=now,
                store_id=store_a.id,
                branch_id=branch.id,
            ),
            m.Expense(
                tenant_id=tenant_id,
                category_id=cat_id,
                category=cat_name,
                description="Store B spend",
                amount=30,
                expense_date=now,
                payment_method="cash",
                status="approved",
                created_by=admin.id,
                approved_by=admin.id,
                approved_at=now,
                store_id=store_b.id,
                branch_id=other_branch.id,
            ),
            m.Expense(
                tenant_id=tenant_id,
                category_id=cat_id,
                category=cat_name,
                description="Unscoped",
                amount=12,
                expense_date=now,
                payment_method="cash",
                status="approved",
                created_by=admin.id,
                approved_by=admin.id,
                approved_at=now,
            ),
        ]
    )
    await db_session.commit()

    by_store = await ac.get(
        f"/api/v1/reports/expenses/summary?store_id={store_a.id}",
        headers=headers,
    )
    assert by_store.status_code == 200, by_store.text
    sdata = by_store.json()["data"]
    assert sdata["store_id"] == store_a.id
    assert sdata["store_name"] == "Store A"
    assert sdata["total_amount"] == 55.0
    assert sdata["count"] == 1

    by_budget = await ac.get(
        f"/api/v1/reports/expenses/budget-vs-actual?store_id={store_a.id}",
        headers=headers,
    )
    assert by_budget.status_code == 200, by_budget.text
    bdata = by_budget.json()["data"]
    assert bdata["store_id"] == store_a.id
    assert bdata["store_name"] == "Store A"
    assert bdata["total_actual"] == 55.0

    with_branch = await ac.get(
        f"/api/v1/reports/expenses/summary?branch_id={branch.id}&store_id={store_a.id}",
        headers=headers,
    )
    assert with_branch.status_code == 200
    assert with_branch.json()["data"]["total_amount"] == 55.0

    mismatch = await ac.get(
        f"/api/v1/reports/expenses/summary?branch_id={other_branch.id}&store_id={store_a.id}",
        headers=headers,
    )
    assert mismatch.status_code == 400

    missing = await ac.get(
        "/api/v1/reports/expenses/summary?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_expense_create_and_patch_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    seed["t1"].expense_approval_threshold = 1
    await db_session.commit()

    store = m.Store(
        tenant_id=tenant_id,
        code="E1",
        name="Expense Store",
        is_active=True,
    )
    db_session.add(store)
    await db_session.commit()

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 42,
            "description": "With store",
            "payment_method": "cash",
            "store_id": store.id,
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]
    assert created.json()["data"]["store_id"] == store.id
    assert created.json()["data"]["status"] == "pending"

    cleared = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=headers,
        json={"clear_store": True},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["store_id"] is None

    set_again = await ac.patch(
        f"/api/v1/expenses/{eid}",
        headers=headers,
        json={"store_id": store.id},
    )
    assert set_again.status_code == 200, set_again.text
    assert set_again.json()["data"]["store_id"] == store.id
