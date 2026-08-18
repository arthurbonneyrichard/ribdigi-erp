"""CustomerPaymentCreate / SupplierPaymentCreate.cheque_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CustomerPaymentCreate, IsoDateQueryValue, SupplierPaymentCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_iso_date_query_schema_for_payment_cheque_date():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-18 ") == "2026-08-18"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_payment_cheque_date_schema():
    omit = CustomerPaymentCreate.model_validate(
        {"customer_id": "c1", "amount": 10, "payment_method": "cheque"}
    )
    assert omit.cheque_date is None
    ok = CustomerPaymentCreate.model_validate(
        {
            "customer_id": "c1",
            "amount": 10,
            "payment_method": "cheque",
            "cheque_date": " 2026-08-01 ",
        }
    )
    assert ok.cheque_date == "2026-08-01"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            CustomerPaymentCreate.model_validate(
                {
                    "customer_id": "c1",
                    "amount": 10,
                    "payment_method": "cheque",
                    "cheque_date": bad,
                }
            )

    supp = SupplierPaymentCreate.model_validate(
        {
            "supplier_id": "s1",
            "amount": 10,
            "payment_method": "cheque",
            "cheque_date": "2026-08-10",
        }
    )
    assert supp.cheque_date == "2026-08-10"
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {
                "supplier_id": "s1",
                "amount": 10,
                "payment_method": "cheque",
                "cheque_date": "",
            }
        )


def test_payment_cheque_date_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Payment cheque date"' in page
    assert "payChequeDate.trim() || null" in page
    assert 'aria-label="Payment cheque number"' in page
    assert 'aria-label="Payment cheque bank name"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Payment cheque_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Payment cheque date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_payment_cheque_date_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Cheque Date Tip Cust {uuid4().hex[:6]}"},
    )
    assert cust.status_code == 200, cust.text
    cust_id = cust.json()["data"]["id"]

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            f"/api/v1/customers/{cust_id}/payments",
            headers=admin,
            json={
                "customer_id": cust_id,
                "amount": 1,
                "payment_method": "cheque",
                "cheque_date": bad,
                "apply_early_discount": False,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "cheque_number": f"CHQ-{uuid4().hex[:8].upper()}",
            "cheque_date": "2026-08-01",
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

    padded = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cheque",
            "cheque_date": " 2026-08-02 ",
            "apply_early_discount": False,
        },
    )
    assert padded.status_code == 200, padded.text

    supp = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Cheque Date Tip Sup {uuid4().hex[:6]}"},
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
            "cheque_date": "",
            "apply_early_discount": False,
        },
    )
    assert blank_s.status_code == 422, blank_s.text

    ok_s = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=admin,
        json={
            "supplier_id": supp_id,
            "amount": 1,
            "payment_method": "cheque",
            "cheque_date": "2026-08-10",
            "apply_early_discount": False,
        },
    )
    assert ok_s.status_code == 200, ok_s.text
