"""OpenAPI honesty tips #1463–#1502: POS/tax/PI/SO/bank money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import bank_connectors as bank_connectors_mod
from app import bank_feed as bank_feed_mod
from app import bank_recon as bank_recon_mod
from app import cheques as cheques_mod
from app import expenses as expenses_mod
from app import pos as pos_mod
from app import purchasing as purchasing_mod
from app import reservations as reservations_mod
from app import sales as sales_mod
from app import sales_docs as sales_docs_mod
from app import tax as tax_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch26_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "POS credit_portion money_json Decimal pilot OpenAPI",
        "POS open_session opening_cash money_json Decimal pilot OpenAPI",
        "POS apply_sale_to_session money_json Decimal pilot OpenAPI",
        "POS close_session actual_cash money_json Decimal pilot OpenAPI",
        "POS resolve_sale_payments money_json Decimal pilot OpenAPI",
        "Expenses scale_monthly_budget money_json Decimal pilot OpenAPI",
        "Tax effective_rate fallback money_json Decimal pilot OpenAPI",
        "Bank recon expected_closing money_json Decimal pilot OpenAPI",
        "Sales invoice tax_breakdown by_rate taxable money_json Decimal pilot OpenAPI",
        "Sales invoice tax_breakdown by_rate tax money_json Decimal pilot OpenAPI",
        "Sales invoice tax_breakdown by_component money_json Decimal pilot OpenAPI",
        "Purchase invoice tax_breakdown by_rate taxable money_json Decimal pilot OpenAPI",
        "Purchase invoice tax_breakdown by_rate tax money_json Decimal pilot OpenAPI",
        "Purchase invoice tax_breakdown by_component money_json Decimal pilot OpenAPI",
        "Purchase invoice balance_due_base money_json Decimal pilot OpenAPI",
        "Purchase invoice balance_due money_json Decimal pilot OpenAPI",
        "Sales order reserved_qty money_json Decimal pilot OpenAPI",
        "Bank connectors sync net money_json Decimal pilot OpenAPI",
        "Bank connectors sync close_bal money_json Decimal pilot OpenAPI",
        "Bank feed line amount money_json Decimal pilot OpenAPI",
        "Bank feed OFX opening infer money_json Decimal pilot OpenAPI",
        "Reservations active_reserved_qty money_json Decimal pilot OpenAPI",
        "Reservations available_qty money_json Decimal pilot OpenAPI",
        "Cheque AR settlement money_json Decimal pilot OpenAPI",
        "Cheque AP settlement money_json Decimal pilot OpenAPI",
        "Accounting Cash transfer next number aria OpenAPI",
        "Accounting Save accounting numbering aria OpenAPI",
        "Accounting Account status filter aria OpenAPI",
        "Accounting Bank connection status filter aria OpenAPI",
        "Accounting Cheque direction filter aria OpenAPI",
        "Accounting Statement opening balance aria OpenAPI",
        "Accounting Statement closing balance aria OpenAPI",
        "Accounting Create bank statement aria OpenAPI",
        "Accounting Create liquid account aria OpenAPI",
        "Accounting P&L from date aria OpenAPI",
        "Accounting P&L to date aria OpenAPI",
        "Accounting Manual journal lines aria OpenAPI",
        "Stores Cash drawer port aria OpenAPI",
        "Stores Store reorder level aria OpenAPI",
        "Stores Store reorder qty aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "credit_portion" in standards
    assert "scale_monthly_budget" in standards or "expected_closing" in standards
    assert "active_reserved_qty" in standards or "reserved_qty" in standards

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash transfer next number"' in accounting
    assert 'aria-label="Account status filter"' in accounting
    assert 'aria-label="Cheque direction filter"' in accounting
    assert 'aria-label="P&L from date"' in accounting

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash drawer port"' in stores
    assert 'aria-label="Store reorder level"' in stores
    assert 'aria-label="Store reorder qty"' in stores


def test_money_json_wired_batch26():
    assert money_json("12.50") == 12.5

    credit_src = inspect.getsource(pos_mod.credit_portion)
    assert "return money_json(" in credit_src

    open_src = inspect.getsource(pos_mod.open_session)
    assert "cash = money_json(round(float(opening_cash or 0), 2))" in open_src

    apply_src = inspect.getsource(pos_mod.apply_sale_to_session)
    assert "amount = money_json(round(float(total or 0), 2))" in apply_src
    assert "part = money_json(round(float(tender.get(\"amount\") or 0), 2))" in apply_src

    close_src = inspect.getsource(pos_mod.close_session)
    assert "actual = money_json(round(float(actual_cash), 2))" in close_src

    resolve_src = inspect.getsource(pos_mod.resolve_sale_payments)
    assert "sale_total = money_json(round(float(total or 0), 2))" in resolve_src
    assert "amount = money_json(round(float(raw.get(\"amount\") or 0), 2))" in resolve_src
    assert "paid = money_json(round(sum(p[\"amount\"] for p in normalized), 2))" in resolve_src

    scale_src = inspect.getsource(expenses_mod.scale_monthly_budget)
    assert "return money_json(float(budget_monthly or 0) * (days / 30.0))" in scale_src

    eff_src = inspect.getsource(tax_mod.effective_rate_from_components)
    assert "return money_json(fallback or 0)" in eff_src

    recon_src = inspect.getsource(bank_recon_mod.complete_statement)
    assert "expected_closing = money_json(round(money_json(stmt.opening_balance or 0) + net, 2))" in recon_src

    si_tax = inspect.getsource(sales_mod._invoice_tax_breakdown)
    assert "bucket[\"taxable\"] = money_json(" in si_tax
    assert "bucket[\"tax\"] = money_json(round(bucket[\"tax\"] + money_json(line_tax), 2))" in si_tax
    assert "cb[\"tax\"] = money_json(round(cb[\"tax\"] + money_json(c.get(\"amount\") or 0), 2))" in si_tax

    pi_tax = inspect.getsource(purchasing_mod._purchase_invoice_tax_breakdown)
    assert "bucket[\"taxable\"] = money_json(" in pi_tax
    assert "bucket[\"tax\"] = money_json(round(bucket[\"tax\"] + money_json(line_tax), 2))" in pi_tax
    assert "cb[\"tax\"] = money_json(round(cb[\"tax\"] + money_json(c.get(\"amount\") or 0), 2))" in pi_tax

    pi_ser = inspect.getsource(purchasing_mod.serialize_purchase_invoice)
    assert "\"balance_due_base\": money_json(" in pi_ser
    assert "\"balance_due\": money_json(max(money_json(inv.total_amount) - paid, 0))" in pi_ser

    so_src = inspect.getsource(sales_docs_mod.serialize_order)
    assert "\"reserved_qty\": money_json(round(sum(money_json(r.quantity) for r in active), 3))" in so_src

    conn_src = inspect.getsource(bank_connectors_mod.sync_connection)
    assert "net = money_json(round(sum(money_json(ln[\"amount\"]) for ln in fresh), 2))" in conn_src
    assert "else money_json(round(open_bal + net, 2))" in conn_src

    feed_src = inspect.getsource(bank_feed_mod.parse_csv_feed)
    assert "\"amount\": money_json(round(money_json(amount), 2))" in feed_src

    ofx_src = inspect.getsource(bank_feed_mod.parse_ofx_feed)
    assert "net = money_json(round(sum(money_json(ln[\"amount\"]) for ln in lines), 2))" in ofx_src
    assert "opening = money_json(round(money_json(closing) - net, 2))" in ofx_src

    res_active = inspect.getsource(reservations_mod.active_reserved_qty)
    assert "return money_json((await db.execute(stmt)).scalar() or 0)" in res_active

    res_avail = inspect.getsource(reservations_mod.available_qty)
    assert "on_hand = money_json(row.quantity or 0)" in res_avail
    assert "return money_json(on_hand - reserved)" in res_avail

    ar_src = inspect.getsource(cheques_mod._reverse_customer_payment)
    assert "settlement = money_json(round(amount + discount, 2))" in ar_src

    ap_src = inspect.getsource(cheques_mod._reverse_supplier_payment)
    assert "settlement = money_json(round(amount + discount, 2))" in ap_src
