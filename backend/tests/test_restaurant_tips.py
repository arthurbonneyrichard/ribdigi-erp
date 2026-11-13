"""Restaurant tips: on the bill, in the drawer, held in 2187, shared out and paid in cash or on payroll."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import models as m
from app import restaurant_tips
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_hrm_desk import _even
from tests.test_restaurant_till_shift import _dish

R = "/api/v1/restaurant"
TODAY = date.today().isoformat()


def test_split_adds_up_to_the_pesewa():
    out = restaurant_tips.split(Decimal("10.00"), {"a": Decimal(1), "b": Decimal(1), "c": Decimal(1)})
    assert sorted(out.values(), reverse=True) == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]
    out = restaurant_tips.split(Decimal("100"), {"a": Decimal(300), "b": Decimal(100)})
    assert out == {"a": Decimal("75.00"), "b": Decimal("25.00")}


async def _user(ac, h, email, role, name):
    r = await ac.post("/api/v1/users", headers=h, json={"email": email, "full_name": name, "password": "SecurePass123!", "role": role})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"], await auth_headers(ac, email=email, tenant_slug="alpha")


async def _setup(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    waiter_id, waiter = await _user(ac, admin, "efua@alpha.example.com", "restaurant_waiter", "Efua")
    cashier_id, cashier = await _user(ac, admin, "kwame@alpha.example.com", "restaurant_cashier", "Kwame")
    dish = await _dish(ac, admin, "Jollof", 50)
    assert (await ac.post(f"{R}/till/shift/open", headers=cashier, json={"opening_cash": 100})).status_code == 200
    return admin, (waiter_id, waiter), (cashier_id, cashier), dish


async def _bill(ac, waiter, cashier, dish, *, tip, method="cash"):
    order = await ac.post(
        f"{R}/orders", headers=waiter,
        json={"service_mode": "takeaway", "payment_method": method, "customer_name": "Ama", "lines": [{"product_id": dish["id"], "quantity": "1"}]},
    )
    assert order.status_code == 200, order.text
    done = await ac.post(f"{R}/orders/{order.json()['data']['id']}/complete", headers=cashier, json={"tip": tip})
    assert done.status_code == 200, done.text
    return done.json()["data"]


async def _held(db_session, tenant_id) -> float:
    value = (await db_session.execute(select(m.Account.balance).where(m.Account.tenant_id == tenant_id, m.Account.code == "2187"))).scalar_one()
    return float(value or 0)


async def test_tip_is_held_for_staff_counted_in_the_drawer_and_paid_by_server(client, db_session):
    ac, seed = client
    admin, (waiter_id, waiter), (cashier_id, cashier), dish = await _setup(ac, seed, db_session)
    bill = await _bill(ac, waiter, cashier, dish, tip=12.5)
    assert bill["tip_amount"] == 12.5 and bill["total_amount"] == 50
    await _bill(ac, waiter, cashier, dish, tip=7.5, method="card")
    shift = (await ac.get(f"{R}/till/shift", headers=cashier)).json()["data"]
    assert shift["cash_tips"] == 12.5 and shift["tips"] == 20 and shift["expected_cash"] == 162.5
    assert abs(await _held(db_session, seed["t1"].id)) == 20

    # Waiters and cashiers cannot share out tips; they see their own.
    assert (await ac.get(f"{R}/tips/runs", headers=waiter)).status_code == 403
    pool = (await ac.get(f"{R}/tips/unshared?date_from={TODAY}&date_to={TODAY}", headers=admin)).json()["data"]
    assert pool["total"] == 20 and pool["tips"] == 2

    run = await ac.post(f"{R}/tips/runs", headers=admin, json={"date_from": TODAY, "date_to": TODAY, "method": "by_server"})
    assert run.status_code == 200, run.text
    run = run.json()["data"]
    assert [(s["user_id"], s["amount"]) for s in run["shares"]] == [(waiter_id, 20)]
    # Nothing is left to share for the same days.
    assert (await ac.post(f"{R}/tips/runs", headers=admin, json={"date_from": TODAY, "date_to": TODAY, "method": "by_server"})).status_code == 409
    assert (await ac.post(f"{R}/tips/runs/{run['id']}/pay", headers=admin, json={"method": "cash"})).status_code == 409
    assert (await ac.post(f"{R}/tips/runs/{run['id']}/approve", headers=admin)).status_code == 200
    paid = await ac.post(f"{R}/tips/runs/{run['id']}/pay", headers=admin, json={"method": "cash"})
    assert paid.status_code == 200 and paid.json()["data"]["status"] == "paid"
    assert await _held(db_session, seed["t1"].id) == 0
    mine = (await ac.get(f"{R}/tips/mine", headers=waiter)).json()["data"]
    assert mine[0]["amount"] == 20 and mine[0]["status"] == "paid"
    await _even(ac, admin)


async def test_equal_split_needs_someone_without_a_share_to_approve_and_cancel_returns_tips(client, db_session):
    ac, seed = client
    admin, (waiter_id, waiter), (cashier_id, cashier), dish = await _setup(ac, seed, db_session)
    await _bill(ac, waiter, cashier, dish, tip=10)
    admin_id = (await ac.get("/api/v1/me", headers=admin)).json()["data"]["id"]
    run = (
        await ac.post(
            f"{R}/tips/runs", headers=admin,
            json={"date_from": TODAY, "date_to": TODAY, "method": "equal", "user_ids": [waiter_id, cashier_id, admin_id]},
        )
    ).json()["data"]
    assert sorted(s["amount"] for s in run["shares"]) == [3.33, 3.33, 3.34]
    blocked = await ac.post(f"{R}/tips/runs/{run['id']}/approve", headers=admin)
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "TIPS_SECOND_PERSON"
    assert (await ac.post(f"{R}/tips/runs/{run['id']}/cancel", headers=admin)).status_code == 200
    pool = (await ac.get(f"{R}/tips/unshared?date_from={TODAY}&date_to={TODAY}", headers=admin)).json()["data"]
    assert pool["total"] == 10


async def test_a_refund_gives_back_the_bill_not_the_tip(client, db_session):
    ac, seed = client
    admin, (_w, waiter), (_c, cashier), dish = await _setup(ac, seed, db_session)
    bill = await _bill(ac, waiter, cashier, dish, tip=5)
    refund = await ac.post(f"{R}/orders/{bill['id']}/refund", headers=admin, json={"reason": "Cold food"})
    assert refund.status_code == 200, refund.text
    assert abs(await _held(db_session, seed["t1"].id)) == 5
    await _even(ac, admin)


async def test_tips_paid_on_payroll_clear_2187_not_wages(client, db_session):
    ac, seed = client
    admin, (waiter_id, waiter), (_c, cashier), dish = await _setup(ac, seed, db_session)
    await _bill(ac, waiter, cashier, dish, tip=40)
    period = datetime.utcnow().strftime("%Y-%m")
    no_record = await ac.post(f"{R}/tips/runs", headers=admin, json={"date_from": TODAY, "date_to": TODAY, "method": "by_server", "pay_by": "payroll", "period": period})
    assert no_record.status_code == 422 and "staff record" in no_record.text
    person = await ac.post(
        "/api/v1/hrm/employees", headers=admin,
        json={"full_name": "Efua", "email": "efua@alpha.example.com", "hired_on": "2024-01-15", "basic_salary": 2000},
    )
    assert person.status_code == 200, person.text
    run = (await ac.post(f"{R}/tips/runs", headers=admin, json={"date_from": TODAY, "date_to": TODAY, "method": "by_server", "pay_by": "payroll", "period": period})).json()["data"]
    assert (await ac.post(f"{R}/tips/runs/{run['id']}/pay", headers=admin, json={"method": "cash"})).status_code == 409
    assert (await ac.post(f"{R}/tips/runs/{run['id']}/approve", headers=admin)).status_code == 200
    payroll = (await ac.post("/api/v1/hrm/payroll", headers=admin, json={"period": period})).json()["data"]
    slip = next(s for s in payroll["slips"] if s["employee_id"] == person.json()["data"]["id"])
    assert slip["tips"] == 40 and slip["gross"] == 2040 and slip["ssnit_employee"] == 110
    assert (await ac.post(f"{R}/tips/runs/{run['id']}/cancel", headers=admin)).status_code == 409
    assert (await ac.post(f"/api/v1/hrm/payroll/{payroll['id']}/approve", headers=admin)).status_code == 200
    assert await _held(db_session, seed["t1"].id) == 0
    runs = (await ac.get(f"{R}/tips/runs", headers=admin)).json()["data"]
    assert next(r for r in runs if r["id"] == run["id"])["status"] == "paid"
    await _even(ac, admin)
