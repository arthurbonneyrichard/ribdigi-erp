"""POS split tender helpers."""

import pytest
from fastapi import HTTPException

from app import pos as pos_svc


def test_resolve_sale_payments_single():
    single = pos_svc.resolve_sale_payments(total=12.5, payment_method="cash", payments=None)
    assert single == [
        {
            "payment_method": "cash",
            "amount": 12.5,
            "reference": None,
            "liquid_account_id": None,
        }
    ]


def test_resolve_sale_payments_split_ok():
    split = pos_svc.resolve_sale_payments(
        total=100,
        payment_method="cash",
        payments=[
            {"payment_method": "cash", "amount": 35},
            {"payment_method": "card", "amount": 65},
        ],
    )
    assert pos_svc.primary_payment_method(split) == "split"
    assert pos_svc.credit_portion(split) == 0
    assert pos_svc.has_cash_tender(split) is True


def test_resolve_sale_payments_mismatch():
    with pytest.raises(HTTPException) as exc:
        pos_svc.resolve_sale_payments(
            total=50,
            payment_method="cash",
            payments=[
                {"payment_method": "cash", "amount": 10},
                {"payment_method": "card", "amount": 10},
            ],
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "PAYMENT_TOTAL_MISMATCH"
    assert exc.value.detail["sale_total"] == 50


def test_credit_portion():
    payments = [
        {"payment_method": "cash", "amount": 20},
        {"payment_method": "credit", "amount": 30},
    ]
    assert pos_svc.credit_portion(payments) == 30
    assert pos_svc.collected_portion(payments) == 20
    assert pos_svc.primary_payment_method(payments) == "split"


def test_sale_settlement_unpaid_partial_paid():
    unpaid = pos_svc.sale_settlement(total=50, payment_method="credit")
    assert unpaid["payment_status"] == "unpaid"
    assert unpaid["paid_amount"] == 0
    assert unpaid["balance_due"] == 50

    partial = pos_svc.sale_settlement(
        total=50,
        payments=[
            {"payment_method": "cash", "amount": 10},
            {"payment_method": "credit", "amount": 40},
        ],
    )
    assert partial["payment_status"] == "partially_paid"
    assert partial["paid_amount"] == 10
    assert partial["balance_due"] == 40

    paid = pos_svc.sale_settlement(total=50, payment_method="cash")
    assert paid["payment_status"] == "paid"
    assert paid["balance_due"] == 0
