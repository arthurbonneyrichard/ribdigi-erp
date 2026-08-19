"""Stage 16 R1: Reports suite fidelity — outline APIs + tenant isolation + UI tab map."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import reports as reports_svc
from app.expenses import ensure_default_categories
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_reports_suite_outline_endpoints(client, db_session):
    """Sales / Inventory / Low Stock / Purchasing / Expenses / Financial / Store Performance."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await ensure_default_categories(db_session, tenant_id)

    store = await create_store(
        db_session, tenant_id=tenant_id, code="S16R1", name="S16 R1 Store"
    )
    await db_session.flush()

    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-S16-R1",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=80,
            tax_amount=8,
            discount_amount=2,
            total_amount=88,
            store_id=store.id,
            posted_at=today,
            created_by=seed["mgr1"].id,
        )
    )

    cat = (
        await db_session.execute(
            select(m.ExpenseCategory).where(
                m.ExpenseCategory.tenant_id == tenant_id,
                m.ExpenseCategory.code == "RENT",
            )
        )
    ).scalar_one()
    db_session.add(
        m.Expense(
            tenant_id=tenant_id,
            category_id=cat.id,
            category=cat.name,
            amount=55,
            description="S16 R1 rent",
            payment_method="cash",
            status="approved",
            expense_date=today,
            created_by=seed["mgr1"].id,
        )
    )
    seed["p1"].reorder_level = 100
    seed["p1"].stock_qty = 2
    await db_session.commit()
    store_id = store.id

    # --- Sales ---
    daily = await ac.get("/api/v1/reports/sales/daily", headers=headers)
    assert daily.status_code == 200, daily.text
    d = daily.json()["data"]
    assert float(d["total_revenue"]) >= 88
    assert d["invoice_count"] >= 1
    assert "tax" in d and "discounts" in d and "net_sales" in d
    assert "previous_day_revenue" in d

    monthly = await ac.get(
        "/api/v1/reports/sales/monthly",
        headers=headers,
        params={"year": today.year, "month": today.month},
    )
    assert monthly.status_code == 200, monthly.text
    mbody = monthly.json()["data"]
    assert "total_revenue" in mbody or "days" in mbody or "by_day" in mbody

    products = await ac.get("/api/v1/reports/sales/products", headers=headers)
    assert products.status_code == 200, products.text

    customers = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert customers.status_code == 200, customers.text
    assert customers.json()["data"]["customer_count"] >= 1

    salesperson = await ac.get("/api/v1/reports/sales/salesperson", headers=headers)
    assert salesperson.status_code == 200, salesperson.text

    # --- Store Performance ---
    by_store = await ac.get("/api/v1/reports/sales/by-store", headers=headers)
    assert by_store.status_code == 200, by_store.text
    stores = by_store.json()["data"].get("stores") or []
    match = next((s for s in stores if s.get("store_id") == store_id), None)
    assert match is not None
    assert float(match["revenue"]) >= 88

    # --- Inventory + Low Stock ---
    balance = await ac.get("/api/v1/reports/inventory/balance", headers=headers)
    assert balance.status_code == 200, balance.text
    bal = balance.json()["data"]
    assert "items" in bal or isinstance(bal, list)

    low = await ac.get("/api/v1/reports/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    low_body = low.json()["data"]
    assert (
        "products" in low_body
        or "warehouse_low_stock" in low_body
        or "items" in low_body
    )

    movements = await ac.get("/api/v1/reports/inventory/movements", headers=headers)
    assert movements.status_code == 200, movements.text
    assert "movements" in movements.json()["data"]

    valuation = await ac.get("/api/v1/reports/inventory/valuation", headers=headers)
    assert valuation.status_code == 200, valuation.text

    # --- Purchasing ---
    assert (await ac.get("/api/v1/reports/purchases/summary", headers=headers)).status_code == 200
    assert (await ac.get("/api/v1/reports/purchases/suppliers", headers=headers)).status_code == 200
    assert (
        await ac.get("/api/v1/reports/purchases/pending-orders", headers=headers)
    ).status_code == 200
    assert (await ac.get("/api/v1/reports/purchases/returns", headers=headers)).status_code == 200

    # --- Expenses ---
    expenses = await ac.get("/api/v1/reports/expenses/summary", headers=headers)
    assert expenses.status_code == 200, expenses.text
    exp = expenses.json()["data"]
    assert float(exp["total_amount"]) >= 55
    assert exp["by_category"]
    assert "budgets" in exp

    # --- Financial ---
    pnl = await ac.get("/api/v1/reports/profit-loss", headers=headers)
    assert pnl.status_code == 200, pnl.text
    pnl_body = pnl.json()["data"]
    assert "revenue" in pnl_body or "net_profit" in pnl_body or "gross_profit" in pnl_body

    assert (await ac.get("/api/v1/reports/cash-flow", headers=headers)).status_code == 200
    bs = await ac.get("/api/v1/reports/balance-sheet", headers=headers)
    assert bs.status_code == 200, bs.text
    bs_body = bs.json()["data"]
    assert "assets" in bs_body or "total_assets" in bs_body

    assert (await ac.get("/api/v1/reports/trial-balance", headers=headers)).status_code == 200

    exportable = await ac.get("/api/v1/reports/exportable", headers=headers)
    assert exportable.status_code == 200, exportable.text
    types = set(exportable.json()["data"]["types"])
    for needed in (
        "sales_daily",
        "sales_by_store",
        "inventory_low_stock",
        "purchases_summary",
        "expenses_summary",
        "profit_loss",
        "cash_flow",
        "balance_sheet",
    ):
        assert needed in types, f"missing exportable {needed}"


@pytest.mark.asyncio
async def test_reports_suite_tenant_isolation(client, db_session):
    """Alpha sales revenue must not appear in beta tenant sales_daily aggregation."""
    ac, seed = client
    headers = await _mgr(ac)
    today = datetime.utcnow().replace(hour=14, minute=0, second=0, microsecond=0)
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            invoice_number="INV-S16-R1-ISO",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=9999,
            tax_amount=0,
            total_amount=9999,
            posted_at=today,
            created_by=seed["mgr1"].id,
        )
    )
    await db_session.commit()

    alpha_http = await ac.get("/api/v1/reports/sales/daily", headers=headers)
    assert alpha_http.status_code == 200
    assert float(alpha_http.json()["data"]["total_revenue"]) >= 9999

    alpha_svc = await reports_svc.sales_daily(db_session, seed["t1"].id, today)
    beta_svc = await reports_svc.sales_daily(db_session, seed["t2"].id, today)
    assert float(alpha_svc["total_revenue"]) >= 9999
    assert float(beta_svc["total_revenue"] or 0) < 9999


def test_reports_ui_tabs_cover_outline():
    """Frontend Reports page tabs map to Stage 16 outline (Credit/Tax packaging in R2)."""
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    for tab in (
        "sales",
        "inventory",
        "purchases",
        "expenses",
        "pnl",
        "cashflow",
        "balancesheet",
        "stores",
    ):
        assert f"'{tab}'" in page, tab
    assert "/reports/sales/by-store" in page
    assert "/reports/inventory/low-stock" in page
    assert "/reports/profit-loss" in page
    assert "/reports/expenses/summary" in page


def test_reports_suite_br_checkboxes_documented():
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 16 R1" in br
    assert "[x] **Daily Sales:**" in br
    assert "[x] Expense summary by category and period" in br
    assert "[x] **Profit & Loss Statement**" in br
