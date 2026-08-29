"""OpenAPI honesty tips #1853–#1883: residual money_json + FE aria."""

from __future__ import annotations

from pathlib import Path

from app.honesty import money_json

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch36_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Tax compute inclusive zero-eff early return money_json Decimal pilot OpenAPI",
        "Tax compute inclusive component gross/tax/net money_json Decimal pilot OpenAPI",
        "Tax compute inclusive component share money_json Decimal pilot OpenAPI",
        "Tax compute exclusive component net/part money_json Decimal pilot OpenAPI",
        "Tax compute simple zero-rate early return money_json Decimal pilot OpenAPI",
        "Tax compute simple inclusive amounts money_json Decimal pilot OpenAPI",
        "Tax compute simple exclusive amounts money_json Decimal pilot OpenAPI",
        "Tax report purchase_reverse_charge money_json Decimal pilot OpenAPI",
        "Tax report reverse_charge_tax aggregate money_json Decimal pilot OpenAPI",
        "Tax report output_tax aggregate money_json Decimal pilot OpenAPI",
        "Tax report input_tax aggregate money_json Decimal pilot OpenAPI",
        "Tax report net_tax aggregate money_json Decimal pilot OpenAPI",
        "Tax report taxable_outputs money_json Decimal pilot OpenAPI",
        "Tax report zero_rated_outputs money_json Decimal pilot OpenAPI",
        "Tax report exempt_outputs money_json Decimal pilot OpenAPI",
        "Tax report taxable_inputs money_json Decimal pilot OpenAPI",
        "Tax compute_line_total line_amount money_json Decimal pilot OpenAPI",
        "Stock count serialize variance money_json Decimal pilot OpenAPI",
        "Stock count complete variance money_json Decimal pilot OpenAPI",
        "Catalog FEFO remaining money_json Decimal pilot OpenAPI",
        "Catalog batch quantity assign money_json Decimal pilot OpenAPI",
        "Catalog FEFO shortfall money_json Decimal pilot OpenAPI",
        "Bank connector debit-credit amount money_json Decimal pilot OpenAPI",
        "Reports budget variance intermediate money_json Decimal pilot OpenAPI",
        "Reports total_variance intermediate money_json Decimal pilot OpenAPI",
        "Accounting P&L income net accumulate money_json Decimal pilot OpenAPI",
        "Accounting P&L expense net accumulate money_json Decimal pilot OpenAPI",
        "Accounting P&L expense total intermediate money_json Decimal pilot OpenAPI",
        "Accounting P&L gross_profit intermediate money_json Decimal pilot OpenAPI",
        "Accounting P&L net_profit intermediate money_json Decimal pilot OpenAPI",
        "Onboarding restore checklist aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "tax compute breakdown intermediate/early-return" in standards
    assert "stock-count serialize/complete variance" in standards
    assert "money_json(round(...))" in standards

    onboarding = (ROOT / "frontend/components/OnboardingChecklist.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Restore onboarding checklist"' in onboarding


def test_money_json_wired_batch36():
    assert money_json("12.50") == 12.5

    tax = (ROOT / "backend/app/tax.py").read_text(encoding="utf-8")
    assert "net = money_json(round(amount, 2))" in tax
    assert "gross = money_json(round(amount, 2))" in tax
    assert "tax = money_json(round(gross * eff / (100.0 + eff), 2))" in tax
    assert "share = money_json(round(tax - allocated, 2))" in tax
    assert (
        "part = money_json(round(running * money_json(c[\"rate\"]) / 100.0, 2))"
        in tax
    )
    assert "tax = money_json(round(net * rate / 100.0, 2))" in tax
    assert (
        "purchase_reverse_charge = money_json(round(purchase_reverse_charge, 2))"
        in tax
    )
    assert (
        "reverse_charge_tax = money_json(round(reverse_charge_tax + purchase_reverse_charge, 2))"
        in tax
    )
    assert (
        "output_tax = money_json(round(output_invoices + output_pos + purchase_reverse_charge, 2))"
        in tax
    )
    assert "input_tax = money_json(round(input_tax, 2))" in tax
    assert "taxable_outputs = money_json(round(taxable_outputs, 2))" in tax
    assert "line_amount = money_json(round(qty * price, 2))" in tax

    stock_counts = (ROOT / "backend/app/stock_counts.py").read_text(encoding="utf-8")
    assert (
        "variance = None if counted is None else money_json(round(counted - expected, 3))"
        in stock_counts
    )
    assert "variance = money_json(round(counted - expected, 3))" in stock_counts

    catalog = (ROOT / "backend/app/catalog.py").read_text(encoding="utf-8")
    assert "batch.quantity = money_json(round(avail - quantity, 6))" in catalog
    assert "remaining = money_json(round(remaining - take, 6))" in catalog
    assert '"shortfall": money_json(remaining)' in catalog

    bank = (ROOT / "backend/app/bank_connectors.py").read_text(encoding="utf-8")
    assert "amount = money_json(round(credit - debit, 2))" in bank

    reports = (ROOT / "backend/app/reports.py").read_text(encoding="utf-8")
    assert "variance = money_json(round(actual - scaled, 2))" in reports
    assert (
        "total_variance = money_json(round(total_actual - total_budget, 2))"
        in reports
    )

    accounting = (ROOT / "backend/app/accounting.py").read_text(encoding="utf-8")
    assert "net = money_json(round(credit - debit, 2))" in accounting
    assert "net = money_json(round(debit - credit, 2))" in accounting
    assert (
        "expense = money_json(round(cogs + operating_expenses, 2))" in accounting
    )
    assert "gross_profit = money_json(round(revenue - cogs, 2))" in accounting
    assert "net_profit = money_json(round(revenue - expense, 2))" in accounting


def test_no_bare_tax_round_assignments():
    """Residual bare round(..., 2) money assigns in tax.py should be gone."""
    tax = (ROOT / "backend/app/tax.py").read_text(encoding="utf-8")
    bare = [
        line.strip()
        for line in tax.splitlines()
        if ("= round(" in line or "else round(" in line)
        and "money_json" not in line
        and not line.strip().startswith("#")
    ]
    assert bare == [], bare
