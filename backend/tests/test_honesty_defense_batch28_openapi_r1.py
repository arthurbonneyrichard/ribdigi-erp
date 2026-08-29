"""OpenAPI honesty tips #1543–#1582: tax/expense/bank/FX money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import bank_recon as bank_recon_mod
from app import customer_groups as customer_groups_mod
from app import emailer as emailer_mod
from app import expenses as expenses_mod
from app import fx as fx_mod
from app import opening_stock as opening_stock_mod
from app import purchase_ocr as purchase_ocr_mod
from app import purchase_suggestions as purchase_suggestions_mod
from app import tax as tax_mod
from app import uom as uom_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch28_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Tax component normalize rate money_json Decimal pilot OpenAPI",
        "Tax effective_rate net sum money_json Decimal pilot OpenAPI",
        "Tax effective_rate all-sum fallback money_json Decimal pilot OpenAPI",
        "Tax compute_tax_breakdown amount money_json Decimal pilot OpenAPI",
        "Tax compute_tax_breakdown rate_pct money_json Decimal pilot OpenAPI",
        "Tax inclusive denom rates money_json Decimal pilot OpenAPI",
        "Tax inclusive share rate money_json Decimal pilot OpenAPI",
        "Tax exclusive component part money_json Decimal pilot OpenAPI",
        "Tax update rate money_json Decimal pilot OpenAPI",
        "Expense default approval auto_t money_json Decimal pilot OpenAPI",
        "Expense default approval l2_t money_json Decimal pilot OpenAPI",
        "Expense steps_required amount money_json Decimal pilot OpenAPI",
        "Expense requires_approval compare money_json Decimal pilot OpenAPI",
        "Expense category budget update money_json Decimal pilot OpenAPI",
        "Bank recon match bank_amt money_json Decimal pilot OpenAPI",
        "Bank recon suggest amt money_json Decimal pilot OpenAPI",
        "Bank recon list clearing bank_total money_json Decimal pilot OpenAPI",
        "Bank recon create clearing bank_total money_json Decimal pilot OpenAPI",
        "FX doc_rate money_json Decimal pilot OpenAPI",
        "FX upsert_rate money_json Decimal pilot OpenAPI",
        "FX resolve_rate explicit money_json Decimal pilot OpenAPI",
        "FX provider quotes money_json Decimal pilot OpenAPI",
        "Customer group discount lookup money_json Decimal pilot OpenAPI",
        "Customer group apply_discount money_json Decimal pilot OpenAPI",
        "Opening stock line qty money_json Decimal pilot OpenAPI",
        "Opening stock unit_cost money_json Decimal pilot OpenAPI",
        "UoM conversion_ratio factor money_json Decimal pilot OpenAPI",
        "UoM to_stock_qty entered money_json Decimal pilot OpenAPI",
        "UoM validate_unit_base ratio money_json Decimal pilot OpenAPI",
        "Purchase OCR amount compare money_json Decimal pilot OpenAPI",
        "Emailer PO line discount money_json Decimal pilot OpenAPI",
        "Expenses Approve expense aria OpenAPI",
        "Expenses Save expense changes aria OpenAPI",
        "Expenses Cancel expense edit aria OpenAPI",
        "Expenses Edit payment method aria OpenAPI",
        "Inventory Product status filter aria OpenAPI",
        "Inventory Add brand aria OpenAPI",
        "Reports Report schedule enabled filter aria OpenAPI",
        "Reports Report schedule frequency filter aria OpenAPI",
        "Credit Payment method aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "tax component/breakdown" in standards or "UoM conversion" in standards
    assert "purchase OCR" in standards or "emailer PO" in standards

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Approve expense"' in expenses
    assert 'aria-label="Save expense changes"' in expenses
    assert 'aria-label="Cancel expense edit"' in expenses
    assert 'aria-label="Edit payment method"' in expenses

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product status filter"' in inventory
    assert 'aria-label="Add brand"' in inventory

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report schedule enabled filter"' in reports
    assert 'aria-label="Report schedule frequency filter"' in reports

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Payment method"' in credit


def test_money_json_wired_batch28():
    assert money_json("12.50") == 12.5

    norm_src = inspect.getsource(tax_mod.normalize_components)
    assert "rate = money_json(item.get(\"rate\") or 0)" in norm_src

    eff_src = inspect.getsource(tax_mod.effective_rate_from_components)
    assert "total += money_json(c.get(\"rate\") or 0)" in eff_src
    assert "sum(money_json(c.get(\"rate\") or 0) for c in components)" in eff_src

    brk_src = inspect.getsource(tax_mod.compute_tax_breakdown)
    assert "amount = money_json(amount or 0)" in brk_src
    assert "else money_json(rate_pct or 0)" in brk_src
    assert "sum(money_json(c[\"rate\"]) for c in net_comps)" in brk_src
    assert "money_json(c[\"rate\"]) / denom" in brk_src
    assert "money_json(c[\"rate\"]) / 100.0" in brk_src

    upd_src = inspect.getsource(tax_mod.update_tax_rate)
    assert "row.rate = money_json(rate)" in upd_src

    def_src = inspect.getsource(expenses_mod.default_approval_levels)
    assert "auto_t = money_json(auto_threshold)" in def_src
    assert "l2_t = max(money_json(l2_threshold), auto_t)" in def_src

    steps_src = inspect.getsource(expenses_mod.steps_required_from_matrix)
    assert "amt = money_json(amount)" in steps_src

    req_src = inspect.getsource(expenses_mod.requires_approval)
    assert "money_json(amount) > money_json(threshold)" in req_src

    cat_src = inspect.getsource(expenses_mod.update_category)
    assert "cat.budget_amount = money_json(budget_amount)" in cat_src

    match_src = inspect.getsource(bank_recon_mod.match_line)
    assert "bank_amt = money_json(round(money_json(line.amount), 2))" in match_src

    # suggest / auto-match uses amt =
    bank_src = Path(bank_recon_mod.__file__).read_text(encoding="utf-8")
    assert "amt = money_json(round(money_json(bl.amount), 2))" in bank_src
    assert "bank_total = money_json(round(sum(money_json(ln.amount) for ln in bank_lines), 2))" in bank_src

    fx_doc = inspect.getsource(fx_mod.doc_rate)
    assert "rate = money_json(getattr(obj, \"exchange_rate\", None) or 1)" in fx_doc

    upsert_src = inspect.getsource(fx_mod.upsert_rate)
    assert "rate = money_json(rate_to_base)" in upsert_src

    resolve_src = inspect.getsource(fx_mod.resolve_rate)
    assert "rate = money_json(explicit_rate)" in resolve_src

    quotes_src = inspect.getsource(fx_mod.fetch_provider_rates)
    assert "money_json(v) for k, v in (data.get(\"rates\") or {}).items()" in quotes_src

    # discount lookup lives in party_group_discount or similar — find via module
    cg_src = Path(customer_groups_mod.__file__).read_text(encoding="utf-8")
    assert "return money_json(group.discount_percent or 0), group" in cg_src
    apply_src = inspect.getsource(customer_groups_mod.apply_discount)
    assert "base = money_json(base_price or 0)" in apply_src
    assert "money_json(discount_percent or 0)" in apply_src

    open_src = inspect.getsource(opening_stock_mod.post_opening_stock)
    assert "qty = money_json(raw.get(\"quantity\") or 0)" in open_src
    assert "unit_cost = money_json(moved.get(\"cost_price\") or 0)" in open_src
    assert "unit_cost = money_json(unit_cost)" in open_src

    factor_src = inspect.getsource(uom_mod.factor_to_root)
    assert "ratio = money_json(unit.conversion_ratio or 0)" in factor_src

    stock_src = inspect.getsource(uom_mod.to_stock_qty)
    assert "qty = money_json(quantity)" in stock_src

    val_src = inspect.getsource(uom_mod.validate_unit_base)
    assert "ratio = money_json(conversion_ratio if conversion_ratio is not None else 1)" in val_src

    ocr_src = inspect.getsource(purchase_ocr_mod.suggest_for_purchase_invoice)
    assert "money_json(ocr_amount) - money_json(inv.total_amount or 0)" in ocr_src

    email_src = Path(emailer_mod.__file__).read_text(encoding="utf-8")
    assert "disc = money_json(item.get(\"discount\") or 0)" in email_src

    # defense-in-depth still on purchase_suggestions even if not tipped
    sug_src = inspect.getsource(purchase_suggestions_mod._product_suggested_qty)
    assert "money_json(reorder_level)" in sug_src
