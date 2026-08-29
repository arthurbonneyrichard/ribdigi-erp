"""OpenAPI honesty tips #1707–#1744: residual money_json + FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import sales as sales_mod
from app import stock_counts as stock_counts_mod
from app import opening_balances as opening_balances_mod
from app import catalog_meta as catalog_meta_mod
from app import reservations as reservations_mod
from app import credit as credit_mod
from app import fx as fx_mod
from app import cash_transfers as cash_transfers_mod
from app import bank_recon as bank_recon_mod
from app import emailer as emailer_mod
from app import api as api_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch32_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Sales AR payment exchange_rate money_json Decimal pilot OpenAPI",
        "Stock count complete expected_qty money_json Decimal pilot OpenAPI",
        "Stock count complete counted_qty money_json Decimal pilot OpenAPI",
        "Opening balance plug credit money_json Decimal pilot OpenAPI",
        "Opening balance plug opening_balance money_json Decimal pilot OpenAPI",
        "Catalog compute_stock_status qty/reorder money_json Decimal pilot OpenAPI",
        "Reservations to_stock quantity money_json Decimal pilot OpenAPI",
        "Credit aging add_to_bucket money_json Decimal pilot OpenAPI",
        "FX to_base amount×rate money_json Decimal pilot OpenAPI",
        "Cash transfer create amount money_json Decimal pilot OpenAPI",
        "Bank recon signed_amount money_json Decimal pilot OpenAPI",
        "Emailer _fmt_money money_json Decimal pilot OpenAPI",
        "API product create opening stock money_json Decimal pilot OpenAPI",
        "API barcode label prices money_json Decimal pilot OpenAPI",
        "API stock adjust/in/out quantity money_json Decimal pilot OpenAPI",
        "API sale price preview list_price money_json Decimal pilot OpenAPI",
        "API legacy tx credit/balance money_json Decimal pilot OpenAPI",
        "API POS line/cart discount money_json Decimal pilot OpenAPI",
        "API POS credit amount/balance money_json Decimal pilot OpenAPI",
        "API bank statement create balances money_json Decimal pilot OpenAPI",
        "API customer open-invoice due money_json Decimal pilot OpenAPI",
        "API supplier open PI/PO due money_json Decimal pilot OpenAPI",
        "API tax calculate rate_pct money_json Decimal pilot OpenAPI",
        "API _money_safe money_json Decimal pilot OpenAPI",
        "Inventory Activate category aria OpenAPI",
        "Inventory Deactivate category aria OpenAPI",
        "Inventory Activate brand aria OpenAPI",
        "Inventory Deactivate brand aria OpenAPI",
        "Inventory Activate unit aria OpenAPI",
        "Inventory Deactivate unit aria OpenAPI",
        "Sales Post credit aria OpenAPI",
        "Sales Post refund aria OpenAPI",
        "Expenses Preview attachment aria OpenAPI",
        "Purchasing Preview invoice attachment aria OpenAPI",
        "Integrations Copy Python verifier aria OpenAPI",
        "Notifications category filter chip aria OpenAPI",
        "Audit Apply filters aria OpenAPI",
        "Login Back to sign in aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "opening-balance plug" in standards or "stock-count complete" in standards
    assert "tax calculate rate_pct" in standards or "list_price preview" in standards

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Activate category ${c.id}" in inventory
    assert "Deactivate category ${c.id}" in inventory
    assert "Activate brand ${b.id}" in inventory
    assert "Deactivate brand ${b.id}" in inventory
    assert "Activate unit ${u.id}" in inventory
    assert "Deactivate unit ${u.id}" in inventory

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Post sales return credit ${r.id}" in sales
    assert "Post sales return refund ${r.id}" in sales

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Preview expense attachment ${r.id}" in expenses

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Preview purchase invoice attachment ${inv.id}" in purchasing

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Copy Python webhook verifier"' in integrations

    notifications = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "Filter notifications by ${c.label}" in notifications

    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Apply audit filters"' in audit

    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Back to sign in"' in login


def test_money_json_wired_batch32():
    assert money_json("12.50") == 12.5

    sales_src = Path(sales_mod.__file__).read_text(encoding="utf-8")
    assert "pay_rate = money_json(exchange_rate)" in sales_src

    complete_src = inspect.getsource(stock_counts_mod.complete_count)
    assert "expected = money_json(item.expected_qty or 0)" in complete_src
    assert "counted = money_json(item.counted_qty or 0)" in complete_src

    open_src = Path(opening_balances_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(existing_plug[\"credit\"])" in open_src
    assert "money_json(plug_account.opening_balance or 0)" in open_src

    status_src = inspect.getsource(catalog_meta_mod.compute_stock_status)
    assert "qty = money_json(stock_qty or 0)" in status_src
    assert "reorder = money_json(reorder_level or 0)" in status_src

    res_src = Path(reservations_mod.__file__).read_text(encoding="utf-8")
    assert "quantity=money_json(item.quantity)" in res_src

    bucket_src = inspect.getsource(credit_mod.add_to_bucket)
    assert "money_json(amount)" in bucket_src
    assert "float(amount)" not in bucket_src

    to_base_src = inspect.getsource(fx_mod.to_base)
    assert "money_json(amount or 0) * money_json(rate or 1)" in to_base_src

    xfer_src = Path(cash_transfers_mod.__file__).read_text(encoding="utf-8")
    assert "amt = money_json(round(money_json(amount or 0), 2))" in xfer_src

    signed_src = inspect.getsource(bank_recon_mod.journal_line_signed_amount)
    assert "money_json(line.debit or 0)" in signed_src
    assert "money_json(line.credit or 0)" in signed_src

    fmt_src = inspect.getsource(emailer_mod._fmt_money)
    assert "money_json(value or 0)" in fmt_src

    api_src = Path(api_mod.__file__).read_text(encoding="utf-8")
    assert "opening = money_json(product.stock_qty)" in api_src
    assert "price=money_json(product.selling_price or 0)" in api_src
    assert "price=money_json(variant.selling_price or product.selling_price or 0)" in api_src
    assert "quantity_delta=money_json(payload.quantity)" in api_src
    assert "quantity=money_json(payload.quantity)" in api_src
    assert "list_price = money_json(" in api_src
    assert "amount=money_json(payload.total or 0)" in api_src
    assert "party.balance = money_json(party.balance or 0) + money_json(payload.total or 0)" in api_src
    assert "line_discount = round(money_json(item.get(\"discount\") or 0), 2)" in api_src
    assert "money_json(item[\"quantity\"]) * money_json(unit_price)" in api_src
    assert "cart_discount = round(money_json(payload.discount_amount or 0), 2)" in api_src
    assert "amount=money_json(credit_amount)" in api_src
    assert "party.balance = money_json(party.balance or 0) + money_json(credit_amount)" in api_src
    assert "if money_json(credit_amount or 0) <= 0:" in api_src
    assert "opening_balance=money_json(payload.opening_balance or 0)" in api_src
    assert "closing_balance=money_json(payload.closing_balance or 0)" in api_src
    assert "due = max(money_json(inv.total_amount) - money_json(inv.paid_amount or 0), 0)" in api_src
    assert "due = max(money_json(po.total_amount) - money_json(po.paid_amount or 0), 0)" in api_src
    assert "rate_pct = money_json(row.rate)" in api_src
    assert "rate_pct = money_json(default.rate)" in api_src
    money_safe_src = inspect.getsource(api_mod._money_safe)
    assert "money_json(value or 0)" in money_safe_src
