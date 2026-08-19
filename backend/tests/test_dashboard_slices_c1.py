"""Stage 82 C1 — Tenant dashboard chart/KPI subroutes."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_dashboard_slice_routes_ok_for_manager(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in (
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/sales-trend",
        "/api/v1/dashboard/top-products",
        "/api/v1/dashboard/expenses",
        "/api/v1/dashboard/stock-alerts",
        "/api/v1/dashboard/user-stats",
    ):
        r = await ac.get(path, headers=headers)
        assert r.status_code == 200, path


@pytest.mark.asyncio
async def test_cashier_sales_trend_omits_user_stats_and_expenses(client):
    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    trend = await ac.get("/api/v1/dashboard/sales-trend", headers=cash)
    assert trend.status_code == 200, trend.text
    data = trend.json()["data"]
    assert "daily_revenue_series" in data or "monthly_revenue_series" in data
    assert "user_stats" not in data

    expenses = await ac.get("/api/v1/dashboard/expenses", headers=cash)
    assert expenses.status_code == 200
    assert "total_expenses" not in expenses.json()["data"]

    users = await ac.get("/api/v1/dashboard/user-stats", headers=cash)
    assert users.status_code == 200
    assert "user_stats" not in users.json()["data"]


@pytest.mark.asyncio
async def test_dashboard_slices_require_auth(client):
    ac, _seed = client
    r = await ac.get("/api/v1/dashboard/summary")
    assert r.status_code in (401, 403)
