from types import SimpleNamespace

from app.purchasing import (
    PURCHASE_RETURN_REASONS,
    derive_po_status,
    purchase_invoice_status,
)
from app.tax import compute_line_total


def test_compute_line_total_with_tax():
    # Line totals live in app.tax; purchasing uses TaxSpec / resolve_product_tax.
    subtotal, tax, total = compute_line_total(10, 5, 10)
    assert subtotal == 50
    assert tax == 5
    assert total == 55


def test_derive_po_status_partial_and_full():
    items = [
        SimpleNamespace(quantity=10, received_qty=4),
        SimpleNamespace(quantity=5, received_qty=0),
    ]
    assert derive_po_status(items) == "partially_received"

    items = [
        SimpleNamespace(quantity=10, received_qty=10),
        SimpleNamespace(quantity=5, received_qty=5),
    ]
    assert derive_po_status(items) == "received"

    items = [
        SimpleNamespace(quantity=10, received_qty=0),
    ]
    assert derive_po_status(items) == "sent"


def test_purchase_return_reasons_cover_br_matrix():
    assert {"damaged", "wrong_item", "expiry", "quality", "other"} <= PURCHASE_RETURN_REASONS


def test_derive_po_status_after_return_reduces_received():
    items = [SimpleNamespace(quantity=10, received_qty=10)]
    assert derive_po_status(items) == "received"
    items[0].received_qty = 7
    assert derive_po_status(items) == "partially_received"
    items[0].received_qty = 0
    assert derive_po_status(items) == "sent"


def test_purchase_invoice_status_paid_partial_unpaid():
    assert purchase_invoice_status(100, 0) == "unpaid"
    assert purchase_invoice_status(100, 40) == "partial"
    assert purchase_invoice_status(100, 100) == "paid"


def test_purchase_invoice_status_overdue():
    from datetime import datetime, timedelta

    past = datetime.utcnow() - timedelta(days=5)
    assert purchase_invoice_status(100, 0, past) == "overdue"
    assert purchase_invoice_status(100, 20, past) == "overdue"
    assert purchase_invoice_status(100, 100, past) == "paid"
