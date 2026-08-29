"""OpenAPI honesty tips #1023–#1062: user CSV defense + convert/audit/export money_json + residual aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.honesty import money_json
from app.schemas import E164PhoneValue, UserFullNameValue, UserPasswordValue
from app import accounting as accounting_mod
from app import backup as backup_mod
from app import cheques as cheques_mod
from app import credit as credit_mod
from app import invoice_print as invoice_print_mod
from app import purchase_requests as purchase_requests_mod
from app import purchasing as purchasing_mod
from app import sales as sales_mod
from app import sales_docs as sales_docs_mod
from app import user_import as user_import_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch15_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "User CSV full name defense-in-depth OpenAPI",
        "User CSV phone defense-in-depth OpenAPI",
        "User CSV temporary password defense-in-depth OpenAPI",
        "Quotation to order convert money_json Decimal pilot OpenAPI",
        "Order to invoice convert money_json Decimal pilot OpenAPI",
        "Sales return post audit money_json Decimal pilot OpenAPI",
        "Journal unpost audit money_json Decimal pilot OpenAPI",
        "Purchase invoice approve reverse-charge money_json Decimal pilot OpenAPI",
        "Sales credit-limit override extras money_json Decimal pilot OpenAPI",
        "Tenant export expense approval threshold money_json Decimal pilot OpenAPI",
        "Tenant export expense L2 threshold money_json Decimal pilot OpenAPI",
        "Tenant export early-pay discount pct money_json Decimal pilot OpenAPI",
        "Purchase request to PO convert money_json Decimal pilot OpenAPI",
        "Invoice print discount money_json Decimal pilot OpenAPI",
        "Invoice print reverse-charge tax money_json Decimal pilot OpenAPI",
        "Cheque early-payment discount money_json Decimal pilot OpenAPI",
        "Credit early-pay settings money_json Decimal pilot OpenAPI",
        "Inventory Save numbering aria OpenAPI",
        "Inventory Set primary image aria OpenAPI",
        "Inventory Remove gallery image aria OpenAPI",
        "Inventory Activate product aria OpenAPI",
        "Inventory Deactivate product aria OpenAPI",
        "Inventory Select lookup product aria OpenAPI",
        "Inventory Remove brand logo aria OpenAPI",
        "Inventory Activate variant aria OpenAPI",
        "Inventory Deactivate variant aria OpenAPI",
        "Inventory Open stock count aria OpenAPI",
        "Inventory Complete stock count aria OpenAPI",
        "Inventory Refresh movements aria OpenAPI",
        "Inventory Refresh warehouse stock aria OpenAPI",
        "Inventory Refresh transfers aria OpenAPI",
        "Inventory Submit transfer aria OpenAPI",
        "Inventory Approve transfer aria OpenAPI",
        "Inventory Ship transfer aria OpenAPI",
        "Inventory Receive transfer aria OpenAPI",
        "Inventory Cancel transfer aria OpenAPI",
        "Sales Save numbering aria OpenAPI",
        "Sales Assign customer group aria OpenAPI",
        "Stores Save branch aria OpenAPI",
        "Users Activate user aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "money_json" in standards
    assert "User CSV" in standards

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save inventory numbering"' in inventory
    assert "Set primary product image" in inventory
    assert "Remove product gallery image" in inventory
    assert 'aria-label="Activate product"' in inventory
    assert 'aria-label="Deactivate product"' in inventory
    assert "Select lookup product" in inventory
    assert "Remove brand logo" in inventory
    assert "Activate variant" in inventory
    assert "Deactivate variant" in inventory
    assert "Open stock count" in inventory
    assert "Complete stock count and post variances" in inventory
    assert 'aria-label="Refresh inventory movements"' in inventory
    assert 'aria-label="Refresh warehouse stock"' in inventory
    assert 'aria-label="Refresh stock transfers"' in inventory
    assert "Submit stock transfer" in inventory
    assert "Approve stock transfer" in inventory
    assert "Ship stock transfer" in inventory
    assert "Receive stock transfer" in inventory
    assert "Cancel stock transfer" in inventory

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save sales numbering"' in sales
    assert 'aria-label="Assign customer group"' in sales

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save branch"' in stores

    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Activate user" in users


def test_user_csv_type_adapters_batch15():
    with pytest.raises(ValidationError):
        TypeAdapter(UserFullNameValue).validate_python("!!!")
    with pytest.raises(ValidationError):
        TypeAdapter(E164PhoneValue).validate_python("123")
    with pytest.raises(ValidationError):
        TypeAdapter(UserPasswordValue).validate_python("http://evil")

    src = inspect.getsource(user_import_mod.validate_import_rows)
    assert "TypeAdapter(UserFullNameValue)" in src
    assert "TypeAdapter(E164PhoneValue)" in src
    assert "TypeAdapter(UserPasswordValue)" in src


def test_money_json_wired_batch15():
    assert money_json("12.50") == 12.5

    q_src = inspect.getsource(sales_docs_mod.convert_quotation_to_order)
    assert "money_json(i.quantity)" in q_src
    assert "money_json(quote.discount_amount" in q_src

    o_src = inspect.getsource(sales_docs_mod.convert_order_to_invoice)
    assert "money_json(i.unit_price)" in o_src
    assert "money_json(order.discount_amount" in o_src

    ret_src = inspect.getsource(sales_docs_mod.post_return)
    assert "money_json(ret.refunded_amount" in ret_src

    unpost = inspect.getsource(accounting_mod.unpost_journal_entry)
    assert "money_json(entry.total_debit" in unpost
    assert "money_json(entry.total_credit" in unpost

    pi_src = inspect.getsource(purchasing_mod.approve_purchase_invoice)
    assert "reverse_charge_tax" in pi_src
    assert "money_json(" in pi_src

    si_src = inspect.getsource(sales_mod.post_sales_invoice)
    assert "money_json(invoice.total_amount)" in si_src
    assert "invoice_total" in si_src

    backup_src = inspect.getsource(backup_mod.collect_tenant_payload)
    assert "expense_approval_threshold" in backup_src
    assert "expense_l2_threshold" in backup_src
    assert "early_pay_discount_pct" in backup_src
    assert "money_json" in backup_src

    pr_src = inspect.getsource(purchase_requests_mod.convert_to_po)
    assert "money_json(item.quantity)" in pr_src

    print_src = Path(invoice_print_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(payload.get("discount_amount"' in print_src
    assert 'money_json(payload.get("reverse_charge_tax"' in print_src

    cheque_src = Path(cheques_mod.__file__).read_text(encoding="utf-8")
    assert 'money_json(getattr(payment, "early_payment_discount"' in cheque_src

    credit_src = inspect.getsource(credit_mod.early_pay_settings)
    assert "early_pay_discount_pct" in credit_src
    assert "money_json(" in credit_src
