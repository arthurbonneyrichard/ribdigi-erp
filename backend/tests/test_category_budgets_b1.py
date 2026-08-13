"""Category budgets + budget vs actual (BR-9.1 / BR-14.4)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import expenses as expenses_svc
from app import models as m
from app.expenses import scale_monthly_budget
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_scale_monthly_budget():
    assert abs(scale_monthly_budget(100, 30) - 100) < 0.01
    assert abs(scale_monthly_budget(100, 15) - 50) < 0.01
    assert abs(scale_monthly_budget(0, 10) - 0) < 0.01


@pytest.mark.asyncio
async def test_patch_category_budget_and_budget_vs_actual(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    await expenses_svc.ensure_default_categories(db_session, tenant_id)
    await db_session.commit()

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    trans = next(c for c in cats.json()["data"] if c["code"] == "TRANS")

    patched = await ac.patch(
        f"/api/v1/expenses/categories/{trans['id']}",
        headers=headers,
        json={"budget_amount": 100},
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["data"]["budget_amount"]) == 100

    created = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "TRAIN", "name": "Training", "budget_amount": 200},
    )
    assert created.status_code == 200, created.text
    assert float(created.json()["data"]["budget_amount"]) == 200

    # Approved spend under TRANS within last few days
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category_id=trans["id"],
            category="Transportation",
            description="Fuel",
            amount=80,
            expense_date=datetime.utcnow() - timedelta(days=2),
            status="approved",
            created_by=seed["admin1"].id,
        )
    )
    # Pending should be ignored
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category_id=trans["id"],
            category="Transportation",
            description="Pending trip",
            amount=999,
            expense_date=datetime.utcnow() - timedelta(days=1),
            status="pending",
            created_by=seed["admin1"].id,
        )
    )
    await db_session.commit()

    from_date = (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%d")
    to_date = datetime.utcnow().strftime("%Y-%m-%d")
    r = await ac.get(
        f"/api/v1/reports/expenses/budget-vs-actual?from_date={from_date}&to_date={to_date}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["period_days"] >= 14
    row = next(x for x in data["rows"] if x["category_id"] == trans["id"])
    assert abs(float(row["budget_monthly"]) - 100) < 0.01
    expected_scaled = scale_monthly_budget(100, data["period_days"])
    assert abs(float(row["budget_scaled"]) - expected_scaled) < 0.01
    assert abs(float(row["actual"]) - 80) < 0.01
    assert row["status"] in {"under_budget", "on_budget", "over_budget"}
    assert data["top_categories"]
    assert any(t["category_id"] == trans["id"] for t in data["top_categories"])

    # 15-day window with no spend → half of monthly budget, actual 0
    half = await ac.get(
        "/api/v1/reports/expenses/budget-vs-actual?from_date=2026-06-01&to_date=2026-06-15",
        headers=headers,
    )
    assert half.status_code == 200
    hdata = half.json()["data"]
    assert hdata["period_days"] == 15
    hrow = next(x for x in hdata["rows"] if x["category_id"] == trans["id"])
    assert abs(float(hrow["budget_scaled"]) - 50) < 0.01
    assert abs(float(hrow["actual"]) - 0) < 0.01

    # Tenant isolation: beta spend must not appear
    assert "Beta" not in r.text
