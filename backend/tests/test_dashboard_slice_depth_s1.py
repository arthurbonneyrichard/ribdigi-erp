"""Stage 84 S1 — dashboard slice depth (expenses by category, credit, cashier shift API)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_expenses_slice_includes_by_category(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard/expenses", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "total_expenses" in data
    assert "expenses_by_category" in data
    assert isinstance(data["expenses_by_category"], list)


@pytest.mark.asyncio
async def test_credit_slice_exposes_outstanding(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard/credit", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "credit_outstanding" in data or "ar_total_due" in data
    assert "credit" in (data.get("sections") or [])


@pytest.mark.asyncio
async def test_cashier_credit_and_expenses_filtered(client):
    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    expenses = await ac.get("/api/v1/dashboard/expenses", headers=cash)
    assert expenses.status_code == 200
    edata = expenses.json()["data"]
    assert "total_expenses" not in edata
    assert "expenses_by_category" not in edata

    credit = await ac.get("/api/v1/dashboard/credit", headers=cash)
    assert credit.status_code == 200
    cdata = credit.json()["data"]
    assert "credit_outstanding" not in cdata
    assert "ar_total_due" not in cdata


@pytest.mark.asyncio
async def test_main_dashboard_includes_slice_depth_for_manager(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "expenses_by_category" in data
    assert "credit_outstanding" in data or "ar_total_due" in data


@pytest.mark.asyncio
async def test_cashier_pos_current_session_endpoint(client):
    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/pos/sessions/current", headers=cash)
    assert r.status_code == 200, r.text
    # No open shift is a valid empty payload (data null)
    body = r.json()
    assert "data" in body
