"""Reports page APIs: empty/populated, dates, tenant isolation, no shared 500."""

from __future__ import annotations

import pytest
from tests.conftest import auth_headers

REPORT_GETS = [
    "/api/v1/reports/summary",
    "/api/v1/reports/sales/products",
    "/api/v1/reports/sales/salesperson",
    "/api/v1/reports/sales/by-store",
    "/api/v1/reports/sales/by-department",
    "/api/v1/reports/inventory/low-stock",
    "/api/v1/reports/purchases/summary",
    "/api/v1/reports/expenses/budget-vs-actual",
    "/api/v1/reports/cash-flow",
    "/api/v1/reports/profit-loss",
    "/api/v1/reports/trial-balance",
    "/api/v1/reports/balance-sheet",
    "/api/v1/reports/sales/customers",
    "/api/v1/reports/schedules",
]


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_summary_does_not_return_generic_500(client):
    ac, _seed = client
    headers = await _admin(ac)
    r = await ac.get("/api/v1/reports/summary", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json().get("detail") != "The server could not complete this request."
    data = r.json()["data"]
    assert "today_sales" in data
    assert "month_sales" in data
    assert "low_stock_report" in data
    assert "expenses_summary" in data
    assert isinstance(data["products_sold"]["products"], list)
    assert data["products_sold"]["total_quantity"] == 0
    assert data["today_sales"]["invoice_count"] == 0
    assert data["today_sales"]["total_revenue"] == 0
    assert data["expenses_summary"]["count"] == 0


@pytest.mark.asyncio
async def test_each_report_type_empty_ok(client):
    ac, _seed = client
    headers = await _admin(ac)
    failures = []
    for path in REPORT_GETS:
        r = await ac.get(path, headers=headers)
        if r.status_code != 200:
            failures.append((path, r.status_code, r.text[:400]))
    assert not failures, failures


@pytest.mark.asyncio
async def test_date_filter_future_window_is_empty_not_error(client):
    ac, _seed = client
    headers = await _admin(ac)
    qs = "from_date=2099-01-01&to_date=2099-01-31"
    paths = [
        f"/api/v1/reports/sales/products?{qs}",
        f"/api/v1/reports/sales/customers?{qs}",
        f"/api/v1/reports/purchases/summary?{qs}",
        f"/api/v1/reports/expenses/budget-vs-actual?{qs}",
        f"/api/v1/reports/cash-flow?{qs}",
        f"/api/v1/reports/profit-loss?{qs}",
        f"/api/v1/reports/summary?{qs}",
    ]
    for path in paths:
        r = await ac.get(path, headers=headers)
        assert r.status_code == 200, f"{path} {r.text}"
        data = r.json()["data"]
        if "total_revenue" in data:
            assert data["total_revenue"] == 0
        if "today_sales" in data:
            assert data["today_sales"]["total_revenue"] == 0


@pytest.mark.asyncio
async def test_invalid_date_is_client_error_not_500(client):
    ac, _seed = client
    headers = await _admin(ac)
    r = await ac.get(
        "/api/v1/reports/sales/products?from_date=not-a-date",
        headers=headers,
    )
    assert r.status_code in {400, 422}, r.text
    assert r.status_code != 500


@pytest.mark.asyncio
async def test_tenant_isolation_excludes_other_company_catalog(client):
    ac, seed = client
    headers = await _admin(ac)
    products = await ac.get("/api/v1/reports/sales/products", headers=headers)
    assert products.status_code == 200, products.text
    skus = {row.get("sku") for row in products.json()["data"].get("products") or []}
    assert "B-1" not in skus
    low = await ac.get("/api/v1/reports/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    names = {row.get("name") for row in low.json()["data"].get("products") or []}
    assert "Beta Widget" not in names
    customers = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert customers.status_code == 200, customers.text
    cust_names = {row.get("name") for row in customers.json()["data"].get("customers") or []}
    assert "Beta Customer" not in cust_names
    # seed invoice INV-B-1 is tenant 2
    assert seed["inv2"].invoice_number == "INV-B-1"


@pytest.mark.asyncio
async def test_summary_populated_uses_posted_invoice_not_hardcoded(client):
    ac, seed = client
    headers = await _admin(ac)
    product = seed["p1"]
    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 20},
    )
    assert stock.status_code == 200, stock.text
    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Report Buyer", "credit_limit": 10000},
    )
    assert cust.status_code == 200, cust.text
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [
                {"product_id": product.id, "quantity": 2, "unit_price": 15},
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    posted = await ac.post(
        f"/api/v1/sales/invoices/{inv.json()['data']['id']}/post",
        headers=headers,
    )
    assert posted.status_code == 200, posted.text
    invoice_total = posted.json()["data"]["total_amount"]

    empty_before_shape = await ac.get(
        "/api/v1/reports/summary?from_date=2099-01-01&to_date=2099-01-31",
        headers=headers,
    )
    assert empty_before_shape.status_code == 200, empty_before_shape.text
    assert empty_before_shape.json()["data"]["today_sales"]["total_revenue"] == 0

    r = await ac.get("/api/v1/reports/summary", headers=headers)
    assert r.status_code == 200, r.text
    today = r.json()["data"]["today_sales"]
    assert today["invoice_count"] >= 1
    assert today["total_revenue"] == invoice_total

    products = await ac.get("/api/v1/reports/sales/products", headers=headers)
    assert products.status_code == 200, products.text
    pdata = products.json()["data"]
    assert pdata["total_revenue"] == invoice_total
    assert any(row["sku"] == "A-1" for row in pdata["products"])


@pytest.mark.asyncio
async def test_ledger_reports_are_coa_math(client):
    ac, _seed = client
    headers = await _admin(ac)
    pnl = await ac.get("/api/v1/reports/profit-loss", headers=headers)
    assert pnl.status_code == 200, pnl.text
    p = pnl.json()["data"]
    assert "accounts" in p
    expected_net = round(float(p["revenue"]) - float(p["expense"]), 2)
    assert p["net_profit"] == expected_net

    tb = await ac.get("/api/v1/reports/trial-balance", headers=headers)
    assert tb.status_code == 200, tb.text
    t = tb.json()["data"]
    assert "rows" in t or "accounts" in t or "lines" in t
    debit = t.get("debit_total", t.get("total_debit"))
    credit = t.get("credit_total", t.get("total_credit"))
    if debit is not None and credit is not None:
        assert abs(float(debit) - float(credit)) < 0.02

    bs = await ac.get("/api/v1/reports/balance-sheet", headers=headers)
    assert bs.status_code == 200, bs.text
    b = bs.json()["data"]
    assert "assets" in b and "liabilities" in b and "equity" in b
