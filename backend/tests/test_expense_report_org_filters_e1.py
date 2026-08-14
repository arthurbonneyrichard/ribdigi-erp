"""Expense report branch/department filters (BR-14.4 / BR-14.5)."""

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
async def test_expense_reports_filter_by_branch_and_department(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    admin = seed["admin1"]

    branch = m.Branch(tenant_id=tenant_id, code="HQ", name="Head Office", is_active=True)
    other = m.Branch(tenant_id=tenant_id, code="EAST", name="East", is_active=True)
    db_session.add_all([branch, other])
    await db_session.flush()
    dept = m.Department(
        tenant_id=tenant_id,
        code="FIN",
        name="Finance",
        branch_id=branch.id,
        is_active=True,
    )
    db_session.add(dept)
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
                description="HQ finance",
                amount=40,
                expense_date=now,
                payment_method="cash",
                status="approved",
                created_by=admin.id,
                approved_by=admin.id,
                approved_at=now,
                branch_id=branch.id,
                department_id=dept.id,
            ),
            m.Expense(
                tenant_id=tenant_id,
                category_id=cat_id,
                category=cat_name,
                description="East only",
                amount=25,
                expense_date=now,
                payment_method="cash",
                status="approved",
                created_by=admin.id,
                approved_by=admin.id,
                approved_at=now,
                branch_id=other.id,
            ),
            m.Expense(
                tenant_id=tenant_id,
                category_id=cat_id,
                category=cat_name,
                description="Unscoped",
                amount=10,
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

    all_sum = await ac.get("/api/v1/reports/expenses/summary", headers=headers)
    assert all_sum.status_code == 200
    assert all_sum.json()["data"]["total_amount"] >= 75

    by_branch = await ac.get(
        f"/api/v1/reports/expenses/summary?branch_id={branch.id}",
        headers=headers,
    )
    assert by_branch.status_code == 200, by_branch.text
    bdata = by_branch.json()["data"]
    assert bdata["branch_id"] == branch.id
    assert bdata["branch_name"] == "Head Office"
    assert bdata["total_amount"] == 40.0
    assert bdata["count"] == 1

    by_dept = await ac.get(
        f"/api/v1/reports/expenses/budget-vs-actual?department_id={dept.id}",
        headers=headers,
    )
    assert by_dept.status_code == 200, by_dept.text
    ddata = by_dept.json()["data"]
    assert ddata["department_id"] == dept.id
    assert ddata["department_name"] == "Finance"
    assert ddata["total_actual"] == 40.0

    both = await ac.get(
        f"/api/v1/reports/expenses/summary?branch_id={branch.id}&department_id={dept.id}",
        headers=headers,
    )
    assert both.status_code == 200
    assert both.json()["data"]["total_amount"] == 40.0

    bad = await ac.get(
        f"/api/v1/reports/expenses/summary?branch_id={other.id}&department_id={dept.id}",
        headers=headers,
    )
    assert bad.status_code == 400

    missing = await ac.get(
        "/api/v1/reports/expenses/summary?branch_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
