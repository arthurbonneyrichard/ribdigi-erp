"""CustomerPaymentCreate / SupplierPaymentCreate.bank_name OpenAPI honesty (cheque)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import CustomerPaymentCreate, SupplierPaymentCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_payment_cheque_bank_name_schema():
    omit = CustomerPaymentCreate.model_validate(
        {"customer_id": "c1", "amount": 10, "payment_method": "cheque"}
    )
    assert omit.bank_name is None
    ok = CustomerPaymentCreate.model_validate(
        {
            "customer_id": "c1",
            "amount": 10,
            "payment_method": "cheque",
            "bank_name": "  Acme Bank  ",
        }
    )
    assert ok.bank_name == "Acme Bank"
    for bad in ("", " ", "!!!", "---", "http://bank.example", "ops@bank.example"):
        with pytest.raises(ValidationError):
            CustomerPaymentCreate.model_validate(
                {
                    "customer_id": "c1",
                    "amount": 10,
                    "payment_method": "cheque",
                    "bank_name": bad,
                }
            )

    supp = SupplierPaymentCreate.model_validate(
        {
            "supplier_id": "s1",
            "amount": 10,
            "payment_method": "cheque",
            "bank_name": "GCB",
        }
    )
    assert supp.bank_name == "GCB"
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {
                "supplier_id": "s1",
                "amount": 10,
                "payment_method": "cheque",
                "bank_name": "",
            }
        )


def test_payment_cheque_bank_name_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Payment cheque bank name"' in page
    assert "payChequeBankName.trim() || null" in page
    assert 'aria-label="Payment cheque number"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Payment cheque bank_name OpenAPI" in agents
    assert "BankNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Payment cheque bank name" in docs
    assert "BankNameValue" in docs


@pytest.mark.asyncio
async def test_payment_cheque_bank_name_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Cheque Bank Tip Cust {uuid4().hex[:6]}"},
    )
    assert cust.status_code == 200, cust.text
    cust_id = cust.json()["data"]["id"]

    blank = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "bank_name": "",
            "apply_early_discount": False,
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "bank_name": "!!!",
            "apply_early_discount": False,
        },
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "bank_name": "http://bank.example",
            "apply_early_discount": False,
        },
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "cheque_number": f"CHQ-{uuid4().hex[:8].upper()}",
            "bank_name": "Acme Bank",
            "apply_early_discount": False,
        },
    )
    assert ok.status_code == 200, ok.text

    omit = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "apply_early_discount": False,
        },
    )
    assert omit.status_code == 200, omit.text

    supp = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Cheque Bank Tip Sup {uuid4().hex[:6]}"},
    )
    assert supp.status_code == 200, supp.text
    supp_id = supp.json()["data"]["id"]

    blank_s = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=admin,
        json={
            "supplier_id": supp_id,
            "amount": 1,
            "payment_method": "cheque",
            "bank_name": "",
            "apply_early_discount": False,
        },
    )
    assert blank_s.status_code == 422, blank_s.text
