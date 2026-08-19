"""Stage 14 E2: expense store/department assignment, filters, and tenant guards."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.org_units import create_department
from app.stores import create_store
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_expense_store_department_assign_filter_and_foreign_dept(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    store = await create_store(
        db_session, tenant_id=tenant_id, code="E2S1", name="E2 Store One"
    )
    dept = await create_department(
        db_session, tenant_id=tenant_id, code="E2D1", name="E2 Ops"
    )
    foreign_dept = await create_department(
        db_session, tenant_id=seed["t2"].id, code="E2FD", name="Beta Dept"
    )
    other_store = await create_store(
        db_session, tenant_id=tenant_id, code="E2S2", name="E2 Store Two"
    )
    await db_session.commit()

    denied = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "General",
            "amount": 12,
            "description": "Foreign dept",
            "payment_method": "cash",
            "department_id": foreign_dept.id,
        },
    )
    assert denied.status_code == 404, denied.text

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "General",
            "amount": 15,
            "description": "Store+dept expense",
            "payment_method": "cash",
            "store_id": store.id,
            "department_id": dept.id,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    expense_id = data["id"]
    assert data["store_id"] == store.id
    assert data["department_id"] == dept.id

    other = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "General",
            "amount": 9,
            "description": "Other store",
            "payment_method": "cash",
            "store_id": other_store.id,
        },
    )
    assert other.status_code == 200, other.text

    by_store = await ac.get(
        "/api/v1/expenses",
        headers=headers,
        params={"store_id": store.id},
    )
    assert by_store.status_code == 200, by_store.text
    store_ids = {r["id"] for r in by_store.json()["data"]}
    assert expense_id in store_ids
    assert other.json()["data"]["id"] not in store_ids

    by_dept = await ac.get(
        "/api/v1/expenses",
        headers=headers,
        params={"department_id": dept.id},
    )
    assert by_dept.status_code == 200, by_dept.text
    assert any(r["id"] == expense_id for r in by_dept.json()["data"])

    # Pending path for patch — raise amount above auto-approve if needed
    pending = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "General",
            "amount": 5000,
            "description": "Needs org patch",
            "payment_method": "cash",
        },
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["data"]["status"] == "pending"
    pid = pending.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/expenses/{pid}",
        headers=headers,
        json={"store_id": store.id, "department_id": dept.id},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["store_id"] == store.id
    assert patched.json()["data"]["department_id"] == dept.id

    cleared = await ac.patch(
        f"/api/v1/expenses/{pid}",
        headers=headers,
        json={"clear_store": True, "clear_department": True},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["store_id"] is None
    assert cleared.json()["data"]["department_id"] is None


@pytest.mark.asyncio
async def test_recurring_copies_org_dimensions_on_generate(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    store = await create_store(
        db_session, tenant_id=tenant_id, code="E2RS", name="Rec Store"
    )
    dept = await create_department(
        db_session, tenant_id=tenant_id, code="E2RD", name="Rec Dept"
    )
    await db_session.commit()

    rec = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category": "Rent",
            "amount": 40,
            "description": "Recurring with org",
            "frequency": "daily",
            "payment_method": "cash",
            "store_id": store.id,
            "department_id": dept.id,
        },
    )
    assert rec.status_code == 200, rec.text
    assert rec.json()["data"]["store_id"] == store.id
    assert rec.json()["data"]["department_id"] == dept.id
    rid = rec.json()["data"]["id"]

    # Force due
    row = await db_session.get(m.RecurringExpense, rid)
    from datetime import datetime, timedelta

    row.next_run_at = datetime.utcnow() - timedelta(hours=1)
    await db_session.commit()

    gen = await ac.post(
        "/api/v1/expenses/recurring/generate",
        headers=headers,
        json={},
    )
    assert gen.status_code == 200, gen.text
    created = gen.json()["data"]
    assert len(created) >= 1
    match = next(e for e in created if e.get("reference", "").startswith("REC-"))
    assert match["store_id"] == store.id
    assert match["department_id"] == dept.id
