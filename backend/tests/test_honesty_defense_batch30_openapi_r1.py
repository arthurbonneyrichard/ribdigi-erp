"""OpenAPI honesty tips #1623–#1662: accounting/purchasing/sales money_json + residual FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import accounting as accounting_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch30_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Accounting stock_qty_for_cogs missing product money_json Decimal pilot OpenAPI",
        "Accounting stock_qty_for_cogs quantity arg money_json Decimal pilot OpenAPI",
        "Accounting stock_qty_for_cogs qty_base return money_json Decimal pilot OpenAPI",
        "Accounting append_cogs money_json Decimal pilot OpenAPI",
        "Accounting SR refund amount money_json Decimal pilot OpenAPI",
        "Accounting AR payment journal amount money_json Decimal pilot OpenAPI",
        "Accounting AR payment journal discount money_json Decimal pilot OpenAPI",
        "Accounting AP payment journal amount money_json Decimal pilot OpenAPI",
        "Accounting AP payment journal discount money_json Decimal pilot OpenAPI",
        "Accounting PR journal total money_json Decimal pilot OpenAPI",
        "Accounting PI journal net money_json Decimal pilot OpenAPI",
        "Accounting PI journal reverse_charge money_json Decimal pilot OpenAPI",
        "Accounting PI journal total/tax money_json Decimal pilot OpenAPI",
        "Accounting PI reversal journal money_json Decimal pilot OpenAPI",
        "Accounting expense journal amount money_json Decimal pilot OpenAPI",
        "Accounting POS sale amount money_json Decimal pilot OpenAPI",
        "Accounting POS sale tax money_json Decimal pilot OpenAPI",
        "Accounting POS tender amount money_json Decimal pilot OpenAPI",
        "Accounting POS COGS qty money_json Decimal pilot OpenAPI",
        "Purchasing line tax qty money_json Decimal pilot OpenAPI",
        "Purchasing line tax unit_price money_json Decimal pilot OpenAPI",
        "Purchasing line tax breakdown money_json Decimal pilot OpenAPI",
        "Purchasing overdue PI status money_json Decimal pilot OpenAPI",
        "Purchasing GRN received_qty money_json Decimal pilot OpenAPI",
        "Purchasing GRN accepted/rejected qty money_json Decimal pilot OpenAPI",
        "Purchasing GRN outstanding money_json Decimal pilot OpenAPI",
        "Purchasing GRN line_gross money_json Decimal pilot OpenAPI",
        "Purchasing supplier payment amount/due money_json Decimal pilot OpenAPI",
        "Purchasing supplier balance/paid apply money_json Decimal pilot OpenAPI",
        "Sales invoice create line money_json Decimal pilot OpenAPI",
        "Sales invoice post stock/balance money_json Decimal pilot OpenAPI",
        "Sales customer payment amount/due/balance money_json Decimal pilot OpenAPI",
        "Sales Create quotation aria OpenAPI",
        "Sales Create order aria OpenAPI",
        "Sales Create invoice aria OpenAPI",
        "Sales Add customer aria OpenAPI",
        "Purchasing Create draft PO aria OpenAPI",
        "Purchasing Post GRN aria OpenAPI",
        "Credit Record payment aria OpenAPI",
        "Accounting Post balanced entry aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "accounting stock_qty_for_cogs" in standards or "POS sale+tender+COGS" in standards
    assert "purchasing line-tax" in standards or "sales SI create+post" in standards

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create quotation"' in sales
    assert 'aria-label="Create order"' in sales
    assert 'aria-label="Create invoice"' in sales
    assert 'aria-label="Add customer"' in sales

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create draft PO"' in purchasing
    assert 'aria-label="Post GRN"' in purchasing

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Record payment"' in credit

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Post balanced entry"' in accounting


def test_money_json_wired_batch30():
    assert money_json("12.50") == 12.5

    qty_src = inspect.getsource(accounting_mod.stock_qty_for_cogs)
    assert "return money_json(quantity or 0)" in qty_src
    assert "quantity=money_json(quantity)" in qty_src
    assert "return money_json(qty_base)" in qty_src

    cogs_src = inspect.getsource(accounting_mod.append_cogs_lines)
    assert "cogs = money_json(round(money_json(cogs or 0), 2))" in cogs_src

    refund_src = inspect.getsource(accounting_mod.post_sales_return_refund_journal)
    assert "amount = money_json(round(money_json(amount), 2))" in refund_src

    ar_src = inspect.getsource(accounting_mod.post_customer_payment_journal)
    assert "amount = money_json(payment.amount)" in ar_src
    assert "discount = money_json(getattr(payment, \"early_payment_discount\", 0) or 0)" in ar_src

    ap_src = inspect.getsource(accounting_mod.post_supplier_payment_journal)
    assert "amount = money_json(payment.amount)" in ap_src
    assert "discount = money_json(getattr(payment, \"early_payment_discount\", 0) or 0)" in ap_src

    pr_src = inspect.getsource(accounting_mod.post_purchase_return_journal)
    assert "total = money_json(purchase_return.total_amount)" in pr_src

    pi_src = inspect.getsource(accounting_mod.post_purchase_invoice_journal)
    assert "money_json(purchase_invoice.subtotal or 0)" in pi_src
    assert "money_json(getattr(purchase_invoice, \"reverse_charge_tax\", 0) or 0)" in pi_src
    assert "total = to_base(money_json(purchase_invoice.total_amount), rate)" in pi_src
    assert "tax = to_base(money_json(purchase_invoice.tax_amount or 0), rate)" in pi_src

    pi_rev = inspect.getsource(accounting_mod.post_purchase_invoice_reversal_journal)
    assert "money_json(purchase_invoice.subtotal or 0)" in pi_rev
    assert "total = to_base(money_json(purchase_invoice.total_amount), rate)" in pi_rev

    exp_src = inspect.getsource(accounting_mod.post_expense_journal)
    assert "amount = money_json(expense.amount)" in exp_src

    pos_src = inspect.getsource(accounting_mod.post_pos_sale_journal)
    assert "amount = money_json(tx.total or 0)" in pos_src
    assert "tax = money_json(tx.tax or 0)" in pos_src
    assert "part = round(money_json(tender.get(\"amount\") or 0), 2)" in pos_src
    assert '"quantity": money_json(it.get("quantity") or 0)' in pos_src

    tax_src = inspect.getsource(purchasing_mod._purchase_line_tax)
    assert "qty = money_json(item.get(\"quantity\") or 0)" in tax_src
    assert "unit = money_json(item.get(\"unit_price\") or 0)" in tax_src
    assert "money_json(breakdown[\"net\"])" in tax_src

    overdue_src = inspect.getsource(purchasing_mod.refresh_overdue_purchase_invoices)
    assert "money_json(inv.total_amount)" in overdue_src
    assert "money_json(inv.paid_amount or 0)" in overdue_src

    derive_src = inspect.getsource(purchasing_mod.derive_po_status)
    assert "money_json(i.received_qty or 0)" in derive_src

    purch_src = Path(purchasing_mod.__file__).read_text(encoding="utf-8")
    assert "received_qty = money_json(raw.get(\"received_qty\") or 0)" in purch_src
    assert "rejected_qty = money_json(raw.get(\"rejected_qty\") or 0)" in purch_src
    assert "outstanding = money_json(po_item.quantity) - money_json(po_item.received_qty or 0)" in purch_src
    assert "line_gross = accepted_qty * money_json(po_item.unit_price) * (" in purch_src
    assert "amount = money_json(amount)" in purch_src
    assert "due = money_json(inv.total_amount) - money_json(inv.paid_amount or 0)" in purch_src
    assert "supplier.balance = max(money_json(supplier.balance or 0) - settlement_base, 0)" in purch_src
    assert "inv.paid_amount = money_json(inv.paid_amount or 0) + apply_amt" in purch_src
    assert "supplier.balance = money_json(supplier.balance or 0) + accepted_value" in purch_src

    sales_src = Path(sales_mod.__file__).read_text(encoding="utf-8")
    assert "quantity=money_json(item[\"quantity\"])" in sales_src
    assert "line_amount = qty * money_json(unit_price)" in sales_src
    assert "line_sub = money_json(breakdown[\"net\"])" in sales_src
    assert "discount = money_json(item.get(\"discount\") or 0)" in sales_src
    assert "quantity=money_json(item.quantity)" in sales_src
    assert "customer.balance = money_json(customer.balance or 0) + inv_base" in sales_src
    assert "due = money_json(invoice.total_amount) - money_json(invoice.paid_amount or 0)" in sales_src
    assert "customer.balance = max(money_json(customer.balance or 0) - settlement_base, 0)" in sales_src
    assert "invoice.paid_amount = money_json(invoice.paid_amount or 0) + apply_amt" in sales_src
