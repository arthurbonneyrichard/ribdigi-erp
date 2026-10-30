"""Restaurant finance screens: expenses, pay suppliers, money and tax over the shared engine."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
BASE = ROOT / "app/(dashboard)/restaurant"
EXP = (BASE / "expenses/page.tsx").read_text(encoding="utf-8")
PAY = (BASE / "payables/page.tsx").read_text(encoding="utf-8")
MONEY = (BASE / "money/page.tsx").read_text(encoding="utf-8")
TAX = (BASE / "tax/page.tsx").read_text(encoding="utf-8")
NAV = (ROOT / "lib/tenantNav.ts").read_text(encoding="utf-8")


def test_expenses_screen_records_approves_and_budgets():
    assert "api('/expenses', {" in EXP
    assert "`/expenses/${row.id}/approve`" in EXP and "`/expenses/${row.id}/reject`" in EXP
    assert "uploadAttachment(`/expenses/${row.id}/attachment`, file)" in EXP
    assert "'/expenses/recurring/generate'" in EXP
    assert "['mobile_money', 'MoMo']" in EXP
    assert "['GAS', 'Gas and fuel']" in EXP
    assert "Buy ingredients under" in EXP


def test_pay_suppliers_uses_supplier_payments():
    assert "/credit/aging?kind=payable" in PAY
    assert "`/suppliers/${id}/payments`" in PAY
    assert "That is more than the" in PAY
    # Restaurant bills cannot go on credit: guest balances only show when old ones exist.
    assert "{!loading && guests.length ? (" in PAY


def test_money_screen_moves_money_and_shows_profit():
    assert "'/accounting/liquid-accounts'" in MONEY
    assert "'/accounting/transfers'" in MONEY
    assert "/accounting/profit-loss?from_date=${from}&to_date=${to}" in MONEY
    assert "Owner puts money in" in MONEY and "Owner takes money out" in MONEY
    assert 'href="/accounting"' in MONEY


def test_tax_screen_sums_and_downloads_return():
    assert "/reports/tax?from_date=${from}&to_date=${to}" in TAX
    assert "report_type: ghana ? 'tax_filing_gh' : 'tax_filing'" in TAX
    assert "Tax you can claim back" in TAX and "Tax to pay" in TAX
    assert "`/tax/rates/${r.id}/default`" in TAX


def test_restaurant_finance_nav_uses_own_screens():
    block = NAV.split("id: 'restaurant-finance'", 1)[1].split("id: 'restaurant-people'", 1)[0]
    for entry in (
        "['Expenses', '/restaurant/expenses', 'expenses']",
        "['Pay suppliers', '/restaurant/payables', 'credit']",
        "['Money', '/restaurant/money', 'accounting']",
        "['Tax', '/restaurant/tax', 'tax']",
    ):
        assert entry in block
    for old in ("'/expenses'", "'/accounting'", "'/tax'", "/credit?kind"):
        assert old not in block


PROFIT = (BASE / "profit/page.tsx").read_text(encoding="utf-8")
HELP = (BASE / "help/page.tsx").read_text(encoding="utf-8")


def test_profit_screen_statement_compare_and_trend():
    assert "/accounting/profit-loss?from_date=${a}&to_date=${b}" in PROFIT
    assert "previousRange(a, b)" in PROFIT
    assert "Food and drink cost" in PROFIT and "Running costs" in PROFIT
    assert "report_type: 'profit_loss'" in PROFIT
    assert "Last six months" in PROFIT and 'className="rd-legend-row"' in PROFIT


def test_help_screen_guides_and_support_requests():
    assert "Record a market run" in HELP and "Prepare the VAT return" in HELP
    assert "'/support/categories'" in HELP and "'/support/tickets'" in HELP
    assert "`/support/tickets/${id}/replies`" in HELP and "`/support/tickets/${id}/close`" in HELP


def test_restaurant_nav_profit_and_help():
    assert "['Profit and loss', '/restaurant/profit', 'accounting']" in NAV
    assert "{ id: 'restaurant-help', label: '', items: [['Help', '/restaurant/help', 'support']] }" in NAV
    block = NAV.split("export const RESTAURANT_NAV_GROUPS", 1)[1].split("\n];", 1)[0]
    assert "/reports?tab=pnl" not in block
