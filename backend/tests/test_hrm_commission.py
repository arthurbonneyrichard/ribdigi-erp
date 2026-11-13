"""Sales commission: net sales from the same source as the salesperson report (FMCG:
delivered orders), approved by someone else, paid on that month's payroll without SSNIT."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import hrm_commission
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_hrm_desk import _even

pytestmark = pytest.mark.asyncio


def test_commission_amount_decimal():
    assert hrm_commission.commission_amount(Decimal("12345.67"), Decimal("2.5")) == Decimal("308.64")


async def _setup(ac, seed, db_session, industry):
    await set_tenant_industry(db_session, seed["t1"], industry)
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    user = (
        await ac.post(
            "/api/v1/users", headers=h,
            json={"email": "seller@alpha.example.com", "full_name": "Seller", "password": "SecurePass123!", "role": "cashier" if industry == "retail" else "fmcg_rep"},
        )
    ).json()["data"]
    person = (
        await ac.post(
            "/api/v1/hrm/employees", headers=h,
            json={"full_name": "Seller", "email": "seller@alpha.example.com", "hired_on": "2024-01-15", "basic_salary": 2000, "commission_percent": 5},
        )
    ).json()["data"]
    return h, user, person


async def test_retail_commission_from_sales_into_payroll(client, db_session):
    ac, seed = client
    h, user, person = await _setup(ac, seed, db_session, "retail")
    customer = m.Party(tenant_id=seed["t1"].id, kind="customer", name="Akua", status="active", credit_limit=0)
    db_session.add(customer)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id, invoice_number="INV-COM-1", customer_id=customer.id, status="posted",
            subtotal=1000, tax_amount=150, total_amount=1150, posted_at=datetime(2026, 10, 10, 12), created_by=user["id"],
        )
    )
    await db_session.commit()
    month = (await ac.get("/api/v1/hrm/commissions?period=2026-10", headers=h)).json()["data"]
    row = next(r for r in month if r["employee_id"] == person["id"])
    assert row["linked_login"] and row["net_sales"] == 1000 and row["commission"] == 50
    staff = await auth_headers(ac, email="seller@alpha.example.com", tenant_slug="alpha")
    assert (await ac.post("/api/v1/hrm/commissions", headers=staff, json={"employee_id": person["id"], "period": "2026-10"})).status_code == 403
    ok = await ac.post("/api/v1/hrm/commissions", headers=h, json={"employee_id": person["id"], "period": "2026-10"})
    assert ok.status_code == 200, ok.text
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = next(s for s in run["slips"] if s["employee_id"] == person["id"])
    assert slip["commission"] == 50 and slip["gross"] == 2050
    assert slip["ssnit_employee"] == 110  # 5.5% of 2,000 basic only
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 200
    again = await ac.post("/api/v1/hrm/commissions", headers=h, json={"employee_id": person["id"], "period": "2026-10"})
    assert again.status_code == 409
    await _even(ac, h)


async def test_fmcg_commission_counts_only_delivered_orders(client, db_session):
    ac, seed = client
    h, user, person = await _setup(ac, seed, db_session, "fmcg")
    outlet = m.Party(tenant_id=seed["t1"].id, kind="customer", name="Outlet", status="active", credit_limit=0)
    db_session.add(outlet)
    await db_session.flush()
    for number, status, total, returned in (("FO-1", "delivered", 1200, 200), ("FO-2", "booked", 999, 0), ("FO-3", "closed", 500, 0)):
        db_session.add(
            m.FmcgOrder(
                tenant_id=seed["t1"].id, order_number=number, customer_id=outlet.id, status=status, subtotal=total,
                discount=0, tax=0, total=total, paid=0, returned=returned, cost_of_goods=0,
                delivered_at=datetime(2026, 10, 12) if status != "booked" else None, created_by=user["id"],
            )
        )
    await db_session.commit()
    month = (await ac.get("/api/v1/hrm/commissions?period=2026-10", headers=h)).json()["data"]
    row = next(r for r in month if r["employee_id"] == person["id"])
    assert row["net_sales"] == 1500  # (1,200 - 200 returned) + 500; the booked order is not counted
    assert row["commission"] == 75
    rows = (await db_session.execute(select(m.HrmCommission))).scalars().all()
    assert rows == []
