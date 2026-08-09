from app.sales import invoice_payment_status


def test_invoice_payment_status_transitions():
    assert invoice_payment_status(100, 0) == "posted"
    assert invoice_payment_status(100, 40) == "partial"
    assert invoice_payment_status(100, 100) == "paid"
    assert invoice_payment_status(100, 100.0000001) == "paid"
    assert invoice_payment_status(100, 0, previous_status="sent") == "sent"
    assert invoice_payment_status(100, 0, previous_status="overdue") == "overdue"
    assert invoice_payment_status(100, 40, previous_status="sent") == "partial"
