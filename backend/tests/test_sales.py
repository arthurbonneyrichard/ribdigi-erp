from datetime import datetime, timedelta

from app.sales import invoice_payment_status


def test_invoice_payment_status_transitions():
    assert invoice_payment_status(100, 0) == "posted"
    assert invoice_payment_status(100, 40) == "partial"
    assert invoice_payment_status(100, 100) == "paid"
    assert invoice_payment_status(100, 100.0000001) == "paid"
    assert invoice_payment_status(100, 0, emailed_at=datetime.utcnow()) == "sent"
    past = datetime.utcnow() - timedelta(days=5)
    assert invoice_payment_status(100, 0, past) == "overdue"
    assert invoice_payment_status(100, 20, past) == "overdue"
    assert invoice_payment_status(100, 0, past, emailed_at=datetime.utcnow()) == "overdue"
