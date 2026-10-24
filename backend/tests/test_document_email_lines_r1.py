"""Document email/print lines show catalog names and labeled dates."""

from __future__ import annotations

from datetime import datetime

from app.document_display import document_item_label, format_tenant_date
from app.emailer import render_purchase_order_bodies, render_sales_invoice_bodies
from app.purchasing import purchase_return_print_html


class _Tenant:
    def __init__(self, date_format: str = "DD/MM/YYYY"):
        self.date_format = date_format


def test_document_item_label_prefers_name_not_uuid():
    uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert document_item_label({"product_id": uuid}) == "Item"
    assert document_item_label({"product_id": uuid, "name": uuid}) == "Item"
    assert (
        document_item_label(
            {"product_id": uuid, "product_name": "Basmati Rice", "sku": "RICE-25"}
        )
        == "Basmati Rice · RICE-25"
    )
    assert (
        document_item_label(
            {
                "product_name": "Tea",
                "variant_name": "Mint",
                "sku": "TEA-M",
            }
        )
        == "Tea (Mint) · TEA-M"
    )


def test_format_tenant_date_uses_company_format():
    value = "2026-08-20T15:04:05"
    assert format_tenant_date(value) == "20/08/2026"
    assert format_tenant_date(value, _Tenant("MM/DD/YYYY")) == "08/20/2026"
    assert format_tenant_date(value, _Tenant("YYYY-MM-DD")) == "2026-08-20"
    assert format_tenant_date(None) == ""
    assert format_tenant_date(datetime(2026, 1, 5, 9, 0, 0), _Tenant()) == "05/01/2026"


def test_po_email_html_has_name_order_date_and_needed_by():
    tenant = _Tenant("MM/DD/YYYY")
    uuid = "11111111-2222-3333-4444-555555555555"
    text, html = render_purchase_order_bodies(
        company_name="Acme",
        currency="GHS",
        supplier_name="Vendor Co",
        tenant=tenant,
        purchase_order={
            "po_number": "PO-9",
            "created_at": "2026-08-10",
            "due_date": "2026-08-24",
            "subtotal": 10,
            "tax_amount": 0,
            "total_amount": 10,
            "items": [
                {
                    "product_id": uuid,
                    "product_name": "Alpha Widget",
                    "sku": "A-1",
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "line_total": 10,
                }
            ],
        },
    )
    assert "Alpha Widget · A-1" in text
    assert "Alpha Widget" in html
    assert uuid not in text and uuid not in html
    assert "Order date: 08/10/2026" in text
    assert "Needed by: 08/24/2026" in text
    assert "when we expect these goods delivered" in html
    assert ">Due " not in html


def test_invoice_email_omits_due_when_unset_and_labels_amount():
    uuid = "11111111-2222-3333-4444-555555555555"
    text, html = render_sales_invoice_bodies(
        company_name="Acme",
        currency="GHS",
        customer_name="Ada",
        invoice={
            "invoice_number": "INV-9",
            "created_at": "2026-08-15",
            "subtotal": 10,
            "tax_amount": 0,
            "discount_amount": 0,
            "total_amount": 10,
            "paid_amount": 0,
            "balance_due": 10,
            "items": [
                {
                    "product_id": uuid,
                    "product_name": "Idle Snack",
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "line_total": 10,
                }
            ],
        },
    )
    assert "Idle Snack" in text
    assert uuid not in text
    assert "Invoice date: 15/08/2026" in text
    assert "Payment due date:" not in text
    assert "Balance due: GHS 10.00" in text
    assert "Needed by" not in text
    assert "Idle Snack" in html


def test_purchase_return_print_uses_product_name():
    uuid = "11111111-2222-3333-4444-555555555555"
    html = purchase_return_print_html(
        {
            "return_number": "PRN-1",
            "debit_note_number": "DN-1",
            "reason": "damaged",
            "status": "posted",
            "total_amount": 4,
            "items": [
                {
                    "product_id": uuid,
                    "product_name": "Basmati Rice",
                    "quantity": 1,
                    "unit_price": 4,
                    "line_total": 4,
                }
            ],
        },
        supplier_name="Vendor Co",
        company_name="Acme",
    )
    assert "Basmati Rice" in html
    assert uuid not in html
