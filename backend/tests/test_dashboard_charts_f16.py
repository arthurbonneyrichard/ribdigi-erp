"""Stage 1 F16 — dashboard daily/monthly revenue chart series (BR-4.3)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import models as m
from app.dashboard_charts import fill_daily_series, fill_monthly_series, load_revenue_chart_series
from tests.conftest import auth_headers


def test_fill_daily_and_monthly_series_zero_fill():
    now = datetime(2026, 8, 9, 15, 0, 0)
    daily = fill_daily_series({"2026-08-09": 12.5, "2026-08-01": 3}, now=now, days=30)
    assert len(daily) == 30
    assert daily[0]["date"] == "2026-07-11"
    assert daily[-1]["date"] == "2026-08-09"
    assert daily[-1]["revenue"] == 12.5
    assert daily[0]["revenue"] == 0.0

    monthly = fill_monthly_series({"2026-08": 100, "2026-01": 40}, now=now, months=12)
    assert len(monthly) == 12
    assert monthly[0]["month"] == "2025-09"
    assert monthly[-1]["month"] == "2026-08"
    assert monthly[-1]["revenue"] == 100.0
    assert monthly[4]["month"] == "2026-01"
    assert monthly[4]["revenue"] == 40.0


@pytest.mark.asyncio
async def test_dashboard_includes_revenue_chart_series(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    now = datetime.utcnow()
    day = now.replace(hour=10, minute=0, second=0, microsecond=0)
    prior_day = day - timedelta(days=2)
    prior_month = (day.replace(day=1) - timedelta(days=1)).replace(hour=12)

    db_session.add_all(
        [
            m.Transaction(
                id="tx-chart-1",
                tenant_id=tid,
                tx_type="pos_sale",
                reference="POS-CHART-1",
                total=25,
                subtotal=25,
                tax=0,
                created_at=day,
                payload={"items": []},
            ),
            m.Transaction(
                id="tx-chart-2",
                tenant_id=tid,
                tx_type="sale",
                reference="SALE-CHART-2",
                total=15,
                subtotal=15,
                tax=0,
                created_at=prior_day,
                payload={},
            ),
            m.Transaction(
                id="tx-chart-3",
                tenant_id=tid,
                tx_type="pos_sale",
                reference="POS-CHART-3",
                total=40,
                subtotal=40,
                tax=0,
                created_at=prior_month,
                payload={},
            ),
        ]
    )
    await db_session.commit()

    series = await load_revenue_chart_series(db_session, tenant_id=tid, now=now)
    daily = series["daily_revenue_series"]
    monthly = series["monthly_revenue_series"]
    assert len(daily) == 30
    assert len(monthly) == 12
    by_day = {p["date"]: p["revenue"] for p in daily}
    assert by_day[day.strftime("%Y-%m-%d")] >= 25
    assert by_day[prior_day.strftime("%Y-%m-%d")] >= 15
    by_month = {p["month"]: p["revenue"] for p in monthly}
    assert by_month[day.strftime("%Y-%m")] >= 25
    assert by_month[prior_month.strftime("%Y-%m")] >= 40

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["daily_revenue_series"]) == 30
    assert len(data["monthly_revenue_series"]) == 12
    assert data["daily_revenue_series"][0]["date"] < data["daily_revenue_series"][-1]["date"]
    assert "revenue" in data["daily_revenue_series"][0]
    assert "month" in data["monthly_revenue_series"][0]
