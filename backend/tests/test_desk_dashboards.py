"""The bakery, FMCG, gym and HRM dashboards: a 14-day trend, yesterday beside today, and
"Needs you now" items that point at the right screen."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app import desk_dashboard as dash
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _as(ac, seed, db_session, industry):
    await set_tenant_industry(db_session, seed["t1"], industry)
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


def test_daily_series_fills_quiet_days_with_zero():
    first = date(2026, 11, 1)
    rows = dash.daily({date(2026, 11, 3): 12.5}, first=first, days=5)
    assert [r["value"] for r in rows] == [0, 0, 12.5, 0, 0]
    assert rows[0]["date"] == "2026-11-01" and rows[-1]["date"] == "2026-11-05"


def test_months_back_ends_this_month():
    assert dash.months_back(3, today=date(2026, 1, 15)) == ["2025-11", "2025-12", "2026-01"]


@pytest.mark.asyncio
async def test_bakery_dashboard_counts_sales_by_day_and_warns_about_the_till(client, seeded, db_session):
    ac, seed = client
    h = await _as(ac, seed, db_session, "bakery")
    tenant_id = seed["t1"].id
    for days_ago, total in ((0, 115), (1, 57.5), (3, 23)):
        db_session.add(
            m.BakerySale(
                tenant_id=tenant_id, sale_number=f"BS-T{days_ago}", payment_method="cash", status="completed",
                subtotal=total, tax=0, total=total, created_at=datetime.utcnow() - timedelta(days=days_ago),
            )
        )
    db_session.add(
        m.BakerySale(
            tenant_id=tenant_id, sale_number="BS-R", payment_method="cash", status="refunded",
            subtotal=999, tax=0, total=999, created_at=datetime.utcnow(),
        )
    )
    await db_session.commit()
    data = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    points = data["trend"]["points"]
    assert len(points) == 14 and points[-1]["value"] == 115 and points[-2]["value"] == 57.5 and points[-4]["value"] == 23
    assert data["sales_yesterday"] == 57.5
    assert any(a["level"] == "warning" and "till is closed" in a["text"] for a in data["attention"])


@pytest.mark.asyncio
async def test_fmcg_dashboard_flags_an_old_unsettled_dispatch(client, seeded, db_session):
    ac, seed = client
    h = await _as(ac, seed, db_session, "fmcg")
    route = (await ac.post("/api/v1/fmcg/routes", headers=h, json={"code": "DASH", "name": "Dash"})).json()["data"]
    dispatch = (await ac.post("/api/v1/fmcg/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]
    row = await db_session.get(m.FmcgDispatch, dispatch["id"])
    row.dispatch_date = date.today() - timedelta(days=2)
    await db_session.commit()
    data = (await ac.get("/api/v1/fmcg/today", headers=h)).json()["data"]
    assert len(data["trend"]["points"]) == 14
    flagged = [a for a in data["attention"] if dispatch["dispatch_number"] in a["text"]]
    assert flagged and flagged[0]["level"] == "warning" and flagged[0]["href"] == "/fmcg?tab=orders"


@pytest.mark.asyncio
async def test_gym_dashboard_counts_visits_and_refusals(client, seeded, db_session):
    ac, seed = client
    h = await _as(ac, seed, db_session, "gym")
    member = (await ac.post("/api/v1/gym/members", headers=h, json={"full_name": "Dash Member"})).json()["data"]
    await ac.post("/api/v1/gym/check-ins", headers=h, json={"member_id": member["id"]})
    db_session.add(m.GymCheckIn(tenant_id=seed["t1"].id, member_id=member["id"], allowed=True, checked_in_at=datetime.utcnow() - timedelta(days=1)))
    await db_session.commit()
    data = (await ac.get("/api/v1/gym/today", headers=h)).json()["data"]
    assert data["refused_today"] == 1
    assert data["visits_yesterday"] == 1 and data["trend"]["points"][-2]["value"] == 1
    assert any("turned away" in a["text"] for a in data["attention"])


@pytest.mark.asyncio
async def test_hrm_dashboard_shows_payroll_by_month_and_what_is_unpaid(client, seeded, db_session):
    ac, seed = client
    h = await _as(ac, seed, db_session, "hrm")
    await ac.post(
        "/api/v1/hrm/employees", headers=h,
        json={"full_name": "Dash Person", "hired_on": "2024-01-01", "basic_salary": 3000, "allowances": 0},
    )
    period = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": period})).json()["data"]
    await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    data = (await ac.get("/api/v1/hrm/summary", headers=h)).json()["data"]
    months = {p["date"]: p["value"] for p in data["trend"]["points"]}
    assert len(months) == 6 and months[period] == 3000 + 390
    assert {a["text"] for a in data["attention"]} >= {f"Salaries for {period} not paid yet", f"PAYE for {period} not paid yet"}
    assert data["attendance_today"]["not_marked"] == 1
