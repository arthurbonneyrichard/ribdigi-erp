"""OpenAPI honesty tips #1263–#1302: inventory/report money_json + risk_reason defense + tab aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative
from app import ai_inventory as ai_inventory_mod
from app import dashboard as dashboard_mod
from app import purchase_suggestions as purchase_suggestions_mod
from app import reports as reports_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch21_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "AI prediction risk_reason defense-in-depth OpenAPI",
        "Inventory balance total_quantity money_json Decimal pilot OpenAPI",
        "Inventory balance total_value money_json Decimal pilot OpenAPI",
        "Inventory balance item value money_json Decimal pilot OpenAPI",
        "Inventory valuation total_quantity money_json Decimal pilot OpenAPI",
        "Inventory valuation total_value money_json Decimal pilot OpenAPI",
        "Inventory expiry total_quantity money_json Decimal pilot OpenAPI",
        "Inventory transfers total_quantity money_json Decimal pilot OpenAPI",
        "Inventory stock counts total_variance_qty money_json Decimal pilot OpenAPI",
        "Inventory stock counts session variance_qty money_json Decimal pilot OpenAPI",
        "Inventory low-stock suggested_order_qty money_json Decimal pilot OpenAPI",
        "Balance sheet retained earnings money_json Decimal pilot OpenAPI",
        "Balance sheet account balance money_json Decimal pilot OpenAPI",
        "Cash flow line inflow money_json Decimal pilot OpenAPI",
        "Cash flow line outflow money_json Decimal pilot OpenAPI",
        "Cash flow outflows money_json Decimal pilot OpenAPI",
        "Cash flow net money_json Decimal pilot OpenAPI",
        "Sales by customer avg_ticket money_json Decimal pilot OpenAPI",
        "Sales by salesperson avg_ticket money_json Decimal pilot OpenAPI",
        "Sales by store avg_ticket money_json Decimal pilot OpenAPI",
        "Sales by department avg_ticket money_json Decimal pilot OpenAPI",
        "Sales returns by_reason total_amount money_json Decimal pilot OpenAPI",
        "Sales returns by_customer total_amount money_json Decimal pilot OpenAPI",
        "Purchases returns by_reason total_amount money_json Decimal pilot OpenAPI",
        "Purchases returns by_supplier total_amount money_json Decimal pilot OpenAPI",
        "Purchases by supplier row total_amount money_json Decimal pilot OpenAPI",
        "Dashboard sales_today money_json Decimal pilot OpenAPI",
        "Dashboard sales_mtd money_json Decimal pilot OpenAPI",
        "AI inventory velocity_per_day money_json Decimal pilot OpenAPI",
        "AI inventory forecast_demand_7 money_json Decimal pilot OpenAPI",
        "Sales Show invoices tab aria OpenAPI",
        "Sales Show quotations tab aria OpenAPI",
        "Sales Show orders tab aria OpenAPI",
        "Sales Show returns tab aria OpenAPI",
        "Purchasing Show requests tab aria OpenAPI",
        "Purchasing Show orders tab aria OpenAPI",
        "Purchasing Show invoices tab aria OpenAPI",
        "Inventory Show products tab aria OpenAPI",
        "Inventory Show transfers tab aria OpenAPI",
        "Reports Show summary tab aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "risk_reason" in standards.lower() or "prediction" in standards.lower()

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show sales ${id} tab`}' in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show purchasing ${id} tab`}' in purchasing

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show inventory ${id} tab`}' in inventory

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show reports ${id} tab`}' in reports


def test_risk_reason_defense_batch21():
    assert optional_honest_narrative(None, label="AI prediction risk reason") is None
    assert (
        optional_honest_narrative("predicted_stockout", label="AI prediction risk reason")
        == "predicted_stockout"
    )
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="AI prediction risk reason")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        optional_honest_narrative("http://evil", label="AI prediction risk reason")

    src = inspect.getsource(purchase_suggestions_mod.create_requests_from_predictions)
    assert "optional_honest_narrative" in src
    assert "AI prediction risk reason" in src
    assert "purchase request notes" in src


def test_money_json_wired_batch21():
    assert money_json("12.50") == 12.5

    bal_src = inspect.getsource(reports_mod.inventory_balance)
    assert "money_json(" in bal_src
    assert "total_quantity" in bal_src
    assert "total_value" in bal_src
    assert "money_json(\n                    round(money_json(p.stock_qty)" in bal_src or (
        "money_json(\n                    round(\n                        money_json(row[\"quantity\"])"
        in bal_src
    )

    val_src = inspect.getsource(reports_mod.inventory_valuation)
    assert "money_json(" in val_src
    assert "total_quantity" in val_src
    assert "total_value" in val_src

    exp_src = inspect.getsource(reports_mod.inventory_expiry)
    assert "money_json(round(total_qty, 3))" in exp_src

    xfer_src = inspect.getsource(reports_mod.inventory_transfers)
    assert "money_json(round(total_qty, 3))" in xfer_src

    count_src = inspect.getsource(reports_mod.inventory_stock_counts)
    assert "money_json(round(variance_qty, 3))" in count_src
    assert "money_json(round(total_variance_qty, 3))" in count_src

    low_src = inspect.getsource(reports_mod.inventory_low_stock)
    assert "money_json(\n                    max(reorder_qty" in low_src

    bs_src = inspect.getsource(reports_mod._balance_sheet_at)
    assert "money_json(round(money_json(bal_by_id.get(a.id, 0)), 2))" in bs_src
    assert "money_json(round(income - expense, 2))" in bs_src

    cf_src = inspect.getsource(reports_mod.cash_flow)
    assert '"inflow": money_json(debit)' in cf_src
    assert '"outflow": money_json(credit)' in cf_src
    assert "money_json(round(money_json(outflows), 2))" in cf_src
    assert "money_json(round(money_json(inflows) - money_json(outflows), 2))" in cf_src

    for fn in (
        reports_mod.sales_by_customer,
        reports_mod.sales_by_salesperson,
        reports_mod.sales_by_store,
        reports_mod.sales_by_department,
    ):
        src = inspect.getsource(fn)
        assert 'money_json(round(row["revenue"] / row["sale_count"], 2))' in src

    ret_src = inspect.getsource(reports_mod.sales_returns_summary)
    assert 'row["total_amount"] = money_json(round(row["total_amount"], 2))' in ret_src

    pret_src = inspect.getsource(reports_mod.purchases_returns_summary)
    assert 'row["total_amount"] = money_json(round(row["total_amount"], 2))' in pret_src

    psup_src = inspect.getsource(reports_mod.purchases_by_supplier)
    assert 'row["total_amount"] = money_json(round(row["total_amount"], 2))' in psup_src

    dash_src = inspect.getsource(dashboard_mod.build_dashboard)
    assert "money_json(round(money_json(sales_today), 2))" in dash_src
    assert "money_json(round(money_json(sales_mtd), 2))" in dash_src

    ai_src = inspect.getsource(ai_inventory_mod.build_product_forecasts)
    assert "money_json(round(money_json(velocity), 6))" in ai_src
    assert "money_json(round(money_json(velocity) * 7, 3))" in ai_src
