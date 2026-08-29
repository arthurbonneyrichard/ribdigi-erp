"""OpenAPI honesty tips #1802–#1852: residual money_json + FE aria."""

from __future__ import annotations

from pathlib import Path

from app.honesty import money_json

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch35_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "PO create totals money_json Decimal pilot OpenAPI",
        "PO amend totals money_json Decimal pilot OpenAPI",
        "GRN rejected_qty money_json Decimal pilot OpenAPI",
        "Supplier payment discount money_json Decimal pilot OpenAPI",
        "Supplier payment settlement_base money_json Decimal pilot OpenAPI",
        "PI from-GRN line money_json Decimal pilot OpenAPI",
        "PI from-GRN header money_json Decimal pilot OpenAPI",
        "PI create totals money_json Decimal pilot OpenAPI",
        "Sales reverse_charge_tax money_json Decimal pilot OpenAPI",
        "Customer payment discount money_json Decimal pilot OpenAPI",
        "Customer payment settlement_base money_json Decimal pilot OpenAPI",
        "Sales docs QT/SO total money_json Decimal pilot OpenAPI",
        "Sales return line money_json Decimal pilot OpenAPI",
        "Sales return excess money_json Decimal pilot OpenAPI",
        "Accounting AR FX settlement money_json Decimal pilot OpenAPI",
        "Accounting AP FX settlement money_json Decimal pilot OpenAPI",
        "Accounting PI journal net money_json Decimal pilot OpenAPI",
        "Accounting POS revenue split money_json Decimal pilot OpenAPI",
        "API POS cart totals money_json Decimal pilot OpenAPI",
        "Opening balance residual money_json Decimal pilot OpenAPI",
        "FX AR plug money_json Decimal pilot OpenAPI",
        "FX AP plug money_json Decimal pilot OpenAPI",
        "Notifications low-stock suggested money_json Decimal pilot OpenAPI",
        "AI expenses MoM pct money_json Decimal pilot OpenAPI",
        "Stores suggested_order_qty money_json Decimal pilot OpenAPI",
        "Reports sales accumulate money_json Decimal pilot OpenAPI",
        "Reports returns accumulate money_json Decimal pilot OpenAPI",
        "Reports low-stock suggested money_json Decimal pilot OpenAPI",
        "Reports pending PO accumulate money_json Decimal pilot OpenAPI",
        "Party contact primary aria OpenAPI",
        "Platform feature module aria OpenAPI",
        "Low-stock suggestion select aria OpenAPI",
        "Report schedule enabled aria OpenAPI",
        "FEFO strict warehouse aria OpenAPI",
        "Cash drawer open on cash sale aria OpenAPI",
        "Use customer group price aria OpenAPI",
        "Sales invoice reverse charge aria OpenAPI",
        "Sales return restock aria OpenAPI",
        "FX auto-refresh aria OpenAPI",
        "Apply early payment discount aria OpenAPI",
        "Bank reconcile pick statement line aria OpenAPI",
        "Bank reconcile pick book line aria OpenAPI",
        "Webhook event aria OpenAPI",
        "Opening stock post journal aria OpenAPI",
        "Warehouse stock include zero aria OpenAPI",
        "Backup schedule enabled aria OpenAPI",
        "POS split tender aria OpenAPI",
        "PO amend notify supplier aria OpenAPI",
        "Purchase invoice reverse charge aria OpenAPI",
        "Company SMTP use TLS aria OpenAPI",
        "Company SMTP use SSL aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "PO create/amend totals" in standards
    assert "money_json(round(...))" in standards

    contacts = (ROOT / "frontend/components/PartyContactsPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Party contact primary"' in contacts

    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert "Platform feature module ${mod}" in platform

    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Low-stock suggestion select"' in reports
    assert 'aria-label="Report schedule enabled"' in reports

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="FEFO strict warehouse"' in stores
    assert 'aria-label="Cash drawer open on cash sale"' in stores

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Use customer group price"' in sales
    assert 'aria-label="Sales invoice reverse charge"' in sales
    assert 'aria-label="Sales return restock"' in sales

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="FX auto-refresh"' in credit
    assert 'aria-label="Apply early payment discount"' in credit

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Bank reconcile pick statement line ${ln.id}" in accounting
    assert "Bank reconcile pick book line ${jl.journal_line_id}" in accounting

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "Webhook event ${ev}" in integrations

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening stock post journal"' in inventory
    assert 'aria-label="Warehouse stock include zero"' in inventory

    backup = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Backup schedule enabled"' in backup

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS split tender"' in pos

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO amend notify supplier"' in purchasing
    assert 'aria-label="Purchase invoice reverse charge"' in purchasing

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMTP use TLS"' in company
    assert 'aria-label="Company SMTP use SSL"' in company


def test_money_json_wired_batch35():
    assert money_json("12.50") == 12.5

    purchasing = (ROOT / "backend/app/purchasing.py").read_text(encoding="utf-8")
    assert "subtotal=money_json(round(subtotal, 2))" in purchasing
    assert "tax_amount=money_json(round(tax_total, 2))" in purchasing
    assert (
        "total_amount=money_json(round(max(subtotal + tax_total - discount_total, 0), 2))"
        in purchasing
    )
    assert "po.subtotal = money_json(round(subtotal, 2))" in purchasing
    assert "rejected_qty = money_json(round(received_qty - accepted_qty, 3))" in purchasing
    assert "discount = money_json(round(due - amount, 2))" in purchasing
    assert "early_payment_discount=money_json(round(total_discount, 2))" in purchasing
    assert "line_net = money_json(round(qty * unit, 2))" in purchasing

    sales = (ROOT / "backend/app/sales.py").read_text(encoding="utf-8")
    assert "reverse_charge_tax=money_json(round(reverse_charge_tax, 2))" in sales
    assert "discount = money_json(round(due - amount, 2))" in sales
    assert "early_payment_discount=money_json(round(total_discount, 2))" in sales

    sales_docs = (ROOT / "backend/app/sales_docs.py").read_text(encoding="utf-8")
    assert (
        "total = money_json(round(subtotal + tax_total - discount_amount, 2))"
        in sales_docs
    )
    assert "line_net = money_json(round(qty * unit, 2))" in sales_docs
    assert "excess = money_json(round(return_total - apply_to_invoice, 2))" in sales_docs

    accounting = (ROOT / "backend/app/accounting.py").read_text(encoding="utf-8")
    assert "cash_doc = money_json(round(settle - disc, 2))" in accounting
    assert "payment.fx_gain_loss = money_json(round(fx_amt, 2))" in accounting
    assert "revenue = money_json(round(amount - tax, 2))" in accounting

    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert (
        "total = money_json(round(subtotal + tax_total - cart_discount, 2))" in api
    )

    opening = (ROOT / "backend/app/opening_balances.py").read_text(encoding="utf-8")
    assert "residual = money_json(round(total_debit - total_credit, 2))" in opening

    fx = (ROOT / "backend/app/fx.py").read_text(encoding="utf-8")
    assert (
        "plug = money_json(round(cash_base + discount_base - ar_base, 2))" in fx
    )
    assert (
        "plug = money_json(round(ap_base - cash_base - discount_base, 2))" in fx
    )

    notifications = (ROOT / "backend/app/notifications.py").read_text(encoding="utf-8")
    assert "money_json(round(reorder - qty, 3))" in notifications

    ai_expenses = (ROOT / "backend/app/ai_expenses.py").read_text(encoding="utf-8")
    assert (
        "money_json(round((recent / prior - 1) * 100, 1))" in ai_expenses
    )

    stores = (ROOT / "backend/app/stores.py").read_text(encoding="utf-8")
    assert "money_json(round(reorder - qty, 3))" in stores

    reports = (ROOT / "backend/app/reports.py").read_text(encoding="utf-8")
    assert (
        'row["quantity"] = money_json(round(row["quantity"] + qty, 3))' in reports
    )
    assert (
        'row["revenue"] = money_json(round(row["revenue"] + revenue, 2))' in reports
    )
    assert "money_json(round(reorder - qty, 3))" in reports
