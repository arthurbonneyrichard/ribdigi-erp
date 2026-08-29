"""OpenAPI honesty tips #1303–#1342: sales-row money_json + stock qty + residual tab aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import ai_inventory as ai_inventory_mod
from app import inventory as inventory_mod
from app import reports as reports_mod
from app import stores as stores_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch22_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Sales monthly change_pct money_json Decimal pilot OpenAPI",
        "Sales by product row quantity money_json Decimal pilot OpenAPI",
        "Sales by product row revenue money_json Decimal pilot OpenAPI",
        "Sales by customer row revenue money_json Decimal pilot OpenAPI",
        "Sales by customer row tax money_json Decimal pilot OpenAPI",
        "Sales by customer invoice_revenue money_json Decimal pilot OpenAPI",
        "Sales by customer invoice_tax money_json Decimal pilot OpenAPI",
        "Sales by customer pos_revenue money_json Decimal pilot OpenAPI",
        "Sales by customer pos_tax money_json Decimal pilot OpenAPI",
        "Sales by salesperson row revenue money_json Decimal pilot OpenAPI",
        "Sales by salesperson row tax money_json Decimal pilot OpenAPI",
        "Sales by store row revenue money_json Decimal pilot OpenAPI",
        "Sales by store row tax money_json Decimal pilot OpenAPI",
        "Sales by department row revenue money_json Decimal pilot OpenAPI",
        "Sales by department row tax money_json Decimal pilot OpenAPI",
        "Purchases pending ordered_qty money_json Decimal pilot OpenAPI",
        "Purchases pending received_qty money_json Decimal pilot OpenAPI",
        "Purchases pending outstanding_qty money_json Decimal pilot OpenAPI",
        "Sales returns row quantity money_json Decimal pilot OpenAPI",
        "Purchases returns row quantity money_json Decimal pilot OpenAPI",
        "Inventory transfers row quantity money_json Decimal pilot OpenAPI",
        "Inventory transfers shipped_qty money_json Decimal pilot OpenAPI",
        "Inventory transfers received_qty money_json Decimal pilot OpenAPI",
        "Inventory transfers by_route quantity money_json Decimal pilot OpenAPI",
        "Warehouse stock suggested_order_qty money_json Decimal pilot OpenAPI",
        "Store inventory suggested_order_qty money_json Decimal pilot OpenAPI",
        "Insufficient warehouse stock available money_json Decimal pilot OpenAPI",
        "Insufficient warehouse stock requested money_json Decimal pilot OpenAPI",
        "Budget vs actual variance_pct money_json Decimal pilot OpenAPI",
        "AI inventory seasonality ratio money_json Decimal pilot OpenAPI",
        "Purchasing Show grn tab aria OpenAPI",
        "Purchasing Show returns tab aria OpenAPI",
        "Inventory Show catalog tab aria OpenAPI",
        "Inventory Show variants tab aria OpenAPI",
        "Inventory Show batches tab aria OpenAPI",
        "Inventory Show counts tab aria OpenAPI",
        "Inventory Show movements tab aria OpenAPI",
        "Reports Show sales tab aria OpenAPI",
        "Reports Show inventory tab aria OpenAPI",
        "Reports Show purchases tab aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "change_pct" in standards or "variance_pct" in standards

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show purchasing ${id} tab`}' in purchasing

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show inventory ${id} tab`}' in inventory

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Show reports ${id} tab`}' in reports


def test_money_json_wired_batch22():
    assert money_json("12.50") == 12.5

    monthly_src = inspect.getsource(reports_mod.sales_monthly)
    assert "money_json(round(((total - prev) / prev) * 100, 2))" in monthly_src

    product_src = inspect.getsource(reports_mod.sales_by_product)
    assert 'row["quantity"] = money_json(round(row["quantity"], 3))' in product_src
    assert 'row["revenue"] = money_json(round(row["revenue"], 2))' in product_src

    for fn in (
        reports_mod.sales_by_customer,
        reports_mod.sales_by_salesperson,
        reports_mod.sales_by_store,
        reports_mod.sales_by_department,
    ):
        src = inspect.getsource(fn)
        assert 'row[key] = money_json(round(row[key], 2))' in src
        assert "money_json(0)" in src

    pending_src = inspect.getsource(reports_mod.purchases_pending_orders)
    assert "ordered_qty = money_json(round(" in pending_src
    assert "received_qty = money_json(round(" in pending_src
    assert "outstanding_qty = money_json(round(" in pending_src

    sret_src = inspect.getsource(reports_mod.sales_returns_summary)
    assert "qty = money_json(round(sum(money_json(i.quantity)" in sret_src

    pret_src = inspect.getsource(reports_mod.purchases_returns_summary)
    assert "qty = money_json(round(sum(money_json(i.quantity)" in pret_src

    xfer_src = inspect.getsource(reports_mod.inventory_transfers)
    assert "qty = money_json(round(sum(money_json(i.quantity)" in xfer_src
    assert "shipped_qty = money_json(round(" in xfer_src
    assert "received_qty = money_json(round(" in xfer_src
    assert 'row["quantity"] = money_json(round(row["quantity"], 3))' in xfer_src

    inv_src = inspect.getsource(inventory_mod.list_warehouse_stock)
    assert "money_json(max(reorder_qty, round(reorder - qty, 3)))" in inv_src
    assert 'INSUFFICIENT_WAREHOUSE_STOCK' in inspect.getsource(
        inventory_mod.apply_warehouse_stock_change
    )
    wh_src = inspect.getsource(inventory_mod.apply_warehouse_stock_change)
    assert '"available": money_json(before)' in wh_src
    assert '"requested": money_json(abs(float(quantity_delta)))' in wh_src

    store_src = inspect.getsource(stores_mod.store_inventory)
    assert "money_json(max(reorder_qty, round(reorder - qty, 3)))" in store_src

    budget_src = inspect.getsource(reports_mod.budget_vs_actual)
    assert "money_json(round((variance / scaled) * 100.0, 1))" in budget_src
    assert "money_json(0)" in budget_src

    season_src = inspect.getsource(ai_inventory_mod.seasonality_hint)
    assert '"ratio": money_json(round(ratio, 3))' in season_src

    forecast_src = inspect.getsource(ai_inventory_mod.build_product_forecasts)
    assert '"confidence": money_json(conf)' in forecast_src
