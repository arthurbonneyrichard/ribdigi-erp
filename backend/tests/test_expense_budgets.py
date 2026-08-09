"""BR-9.1 expense category budget allocation and period variance."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app import models as m
from app.expenses import category_budget_variance, ensure_default_categories
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_set_category_budget_and_variance(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    await ensure_default_categories(db_session, tenant_id)
    await db_session.commit()

    listed = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert listed.status_code == 200, listed.text
    rent = next(c for c in listed.json()["data"] if c["code"] == "RENT")

    patched = await ac.patch(
        f"/api/v1/expenses/categories/{rent['id']}",
        headers=headers,
        json={"budget_amount": 1000},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["budget_amount"] == 1000

    custom = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "travel", "name": "Travel", "budget_amount": 250},
    )
    assert custom.status_code == 200, custom.text
    assert custom.json()["data"]["code"] == "TRAVEL"
    assert custom.json()["data"]["budget_amount"] == 250
    travel_id = custom.json()["data"]["id"]

    # Auto-approved low amount against Travel
    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": travel_id,
            "amount": 80,
            "description": "Taxi",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["status"] == "approved"

    # Larger pending expense against Rent
    pending = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category_id": rent["id"],
            "amount": 400,
            "description": "Shop rent installment",
            "payment_method": "bank_transfer",
        },
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["data"]["status"] == "pending"

    budgets = await ac.get("/api/v1/expenses/budgets", headers=headers)
    assert budgets.status_code == 200, budgets.text
    body = budgets.json()["data"]
    by_id = {c["id"]: c for c in body["categories"]}
    assert by_id[travel_id]["budget_amount"] == 250
    assert by_id[travel_id]["spent"] == 80
    assert by_id[travel_id]["variance"] == 170
    assert by_id[rent["id"]]["budget_amount"] == 1000
    assert by_id[rent["id"]]["pending"] == 400
    assert by_id[rent["id"]]["spent"] == 0
    assert body["totals"]["spent"] >= 80

    report = await ac.get("/api/v1/reports/expenses/summary", headers=headers)
    assert report.status_code == 200, report.text
    assert "budgets" in report.json()["data"]
    assert report.json()["data"]["budgets"]["totals"]["spent"] >= 80


@pytest.mark.asyncio
async def test_category_budget_over_flag(db_session, seeded):
    tenant_id = seeded["t1"].id
    await ensure_default_categories(db_session, tenant_id)
    cat = (
        await db_session.execute(
            select(m.ExpenseCategory).where(
                m.ExpenseCategory.tenant_id == tenant_id,
                m.ExpenseCategory.code == "UTIL",
            )
        )
    ).scalar_one()
    cat.budget_amount = 50
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category_id=cat.id,
            category=cat.name,
            description="Power",
            amount=75,
            status="approved",
            expense_date=datetime.utcnow(),
            payment_method="cash",
        )
    )
    await db_session.commit()

    result = await category_budget_variance(db_session, tenant_id)
    util = next(c for c in result["categories"] if c["code"] == "UTIL")
    assert util["over_budget"] is True
    assert util["spent"] == 75
    assert util["variance"] == -25
