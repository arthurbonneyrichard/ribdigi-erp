"""OpenAPI honesty tips #1503–#1542: POS/bank/FX/cheque money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import accounting as accounting_mod
from app import backup as backup_mod
from app import bank_connectors as bank_connectors_mod
from app import bank_recon as bank_recon_mod
from app import catalog_meta as catalog_meta_mod
from app import cheques as cheques_mod
from app import customer_groups as customer_groups_mod
from app import fx as fx_mod
from app import opening_balances as opening_balances_mod
from app import pos as pos_mod
from app import stock_counts as stock_counts_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch27_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "POS shift_report sale total money_json Decimal pilot OpenAPI",
        "POS shift_report sale tax money_json Decimal pilot OpenAPI",
        "POS shift_report sale subtotal money_json Decimal pilot OpenAPI",
        "POS shift_report discount_amount money_json Decimal pilot OpenAPI",
        "POS shift_report line_discounts money_json Decimal pilot OpenAPI",
        "POS shift_report discounts money_json Decimal pilot OpenAPI",
        "Bank recon create opening_balance money_json Decimal pilot OpenAPI",
        "Bank recon create closing_balance money_json Decimal pilot OpenAPI",
        "Bank recon create line amount money_json Decimal pilot OpenAPI",
        "Bank recon import net money_json Decimal pilot OpenAPI",
        "Bank recon import open_bal money_json Decimal pilot OpenAPI",
        "Bank recon import close_bal money_json Decimal pilot OpenAPI",
        "Bank connectors http_json opening money_json Decimal pilot OpenAPI",
        "Bank connectors http_json closing money_json Decimal pilot OpenAPI",
        "FX resolve_rate money_json Decimal pilot OpenAPI",
        "Cheque AR create amount money_json Decimal pilot OpenAPI",
        "Cheque AP create amount money_json Decimal pilot OpenAPI",
        "Cheque deposit amount money_json Decimal pilot OpenAPI",
        "Cheque clear amount money_json Decimal pilot OpenAPI",
        "Journal post debit money_json Decimal pilot OpenAPI",
        "Journal post credit money_json Decimal pilot OpenAPI",
        "Opening balance line amount money_json Decimal pilot OpenAPI",
        "Stock count expected_qty money_json Decimal pilot OpenAPI",
        "Stock count counted_qty money_json Decimal pilot OpenAPI",
        "Backup verify actual money_json Decimal pilot OpenAPI",
        "Accounting COGS variant cost money_json Decimal pilot OpenAPI",
        "Accounting COGS product cost money_json Decimal pilot OpenAPI",
        "Customer group create discount money_json Decimal pilot OpenAPI",
        "Customer group update discount money_json Decimal pilot OpenAPI",
        "Catalog unit conversion_ratio fallback money_json Decimal pilot OpenAPI",
        "Inventory Catalog brand status filter aria OpenAPI",
        "Inventory Catalog category status filter aria OpenAPI",
        "Inventory Catalog unit status filter aria OpenAPI",
        "Inventory Product variant status filter aria OpenAPI",
        "Purchasing Purchase return status filter aria OpenAPI",
        "Accounting Cheque status filter aria OpenAPI",
        "Tax Tax rate status filter aria OpenAPI",
        "Integrations Webhook status filter aria OpenAPI",
        "POS Close shift report aria OpenAPI",
        "POS Load shift report aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "shift_report" in standards
    assert "resolve_rate" in standards
    assert "counted" in standards or "expected_qty" in standards

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Catalog brand status filter"' in inventory
    assert 'aria-label="Catalog category status filter"' in inventory
    assert 'aria-label="Catalog unit status filter"' in inventory
    assert 'aria-label="Product variant status filter"' in inventory

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase return status filter"' in purchasing

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cheque status filter"' in accounting

    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax rate status filter"' in tax

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Webhook status filter"' in integrations

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Close POS shift report"' in pos
    assert "Load POS shift report" in pos
    assert "Hide POS shift report" in pos


def test_money_json_wired_batch27():
    assert money_json("12.50") == 12.5

    shift_src = inspect.getsource(pos_mod.shift_report)
    assert 'cart_disc = money_json(payload.get("discount_amount") or 0)' in shift_src
    assert 'line_disc = money_json(payload.get("line_discounts") or 0)' in shift_src
    assert "subtotal = money_json(s.subtotal or 0)" in shift_src
    assert "tax = money_json(s.tax or 0)" in shift_src
    assert "total = money_json(s.total or 0)" in shift_src
    assert '"discount_amount": money_json(cart_disc)' in shift_src
    assert '"line_discounts": money_json(line_disc)' in shift_src
    assert '"discounts": money_json(disc)' in shift_src

    create_src = inspect.getsource(bank_recon_mod.create_statement)
    assert "opening_balance=money_json(opening_balance or 0)" in create_src
    assert "closing_balance=money_json(closing_balance or 0)" in create_src
    assert "amount = money_json(raw.get(\"amount\") or 0)" in create_src

    import_src = inspect.getsource(bank_recon_mod.import_statement_from_feed)
    assert "net = money_json(round(sum(money_json(ln[\"amount\"]) for ln in lines), 2))" in import_src
    assert "money_json(opening_balance)" in import_src
    assert "close_bal = money_json(closing_balance)" in import_src or "money_json(parsed[\"closing_balance\"])" in import_src

    http_src = inspect.getsource(bank_connectors_mod._fetch_http_json)
    assert "money_json(opening) if opening is not None else None" in http_src
    assert "money_json(closing) if closing is not None else None" in http_src

    fx_src = inspect.getsource(fx_mod.resolve_rate)
    assert "return code, money_json(row.rate_to_base)" in fx_src

    ar_src = inspect.getsource(cheques_mod.create_from_customer_payment)
    assert "amount=money_json(payment.amount)" in ar_src

    ap_src = inspect.getsource(cheques_mod.create_from_supplier_payment)
    assert "amount=money_json(payment.amount)" in ap_src

    dep_src = inspect.getsource(cheques_mod.deposit_cheque)
    assert "amount = money_json(cheque.amount)" in dep_src

    clear_src = inspect.getsource(cheques_mod.clear_cheque)
    assert "amount = money_json(cheque.amount)" in clear_src

    journal_src = inspect.getsource(accounting_mod.post_journal_entry)
    assert "debit = money_json(line.get(\"debit\") or 0)" in journal_src
    assert "credit = money_json(line.get(\"credit\") or 0)" in journal_src

    open_src = inspect.getsource(opening_balances_mod.post_coa_opening_balances)
    assert "amount = money_json(raw.get(\"amount\") or 0)" in open_src

    count_create = inspect.getsource(stock_counts_mod.create_count)
    assert "expected_qty=money_json(stock.quantity or 0)" in count_create

    count_upd = inspect.getsource(stock_counts_mod.update_count_items)
    assert "qty = money_json(raw.get(\"counted_qty\"))" in count_upd
    assert "line.counted_qty = money_json(round(qty, 3))" in count_upd

    backup_src = inspect.getsource(backup_mod.prove_restore_integrity)
    assert "else money_json(actual)" in backup_src

    cost_src = inspect.getsource(accounting_mod.unit_cost_for_line)
    assert "v_cost = money_json(variant.cost_price or 0)" in cost_src
    assert "return money_json(product.cost_price or 0)" in cost_src

    cg_create = inspect.getsource(customer_groups_mod.create_group)
    assert "pct = money_json(discount_percent or 0)" in cg_create

    cg_upd = inspect.getsource(customer_groups_mod.update_group)
    assert "pct = money_json(discount_percent)" in cg_upd

    unit_src = inspect.getsource(catalog_meta_mod.update_unit)
    assert "else money_json(row.conversion_ratio or 1)" in unit_src
