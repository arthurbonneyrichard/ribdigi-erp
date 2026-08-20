"""CustomerPaymentCreate / SupplierPaymentCreate reference + notes OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import CustomerPaymentCreate, SupplierPaymentCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_payment_reference_notes_schema():
    create_omit = CustomerPaymentCreate.model_validate(
        {"customer_id": "c1", "amount": 10, "payment_method": "cash"}
    )
    assert create_omit.reference is None
    assert create_omit.notes is None

    create_ok = CustomerPaymentCreate.model_validate(
        {
            "customer_id": "c1",
            "amount": 10,
            "payment_method": "cash",
            "reference": "  REF-1001  ",
            "notes": "  Paid at counter  ",
        }
    )
    assert create_ok.reference == "REF-1001"
    assert create_ok.notes == "Paid at counter"

    for bad in ("", " ", "!!!", "---", "http://pay.example", "ref@bank"):
        with pytest.raises(ValidationError):
            CustomerPaymentCreate.model_validate(
                {
                    "customer_id": "c1",
                    "amount": 10,
                    "payment_method": "cash",
                    "reference": bad,
                }
            )
        with pytest.raises(ValidationError):
            CustomerPaymentCreate.model_validate(
                {
                    "customer_id": "c1",
                    "amount": 10,
                    "payment_method": "cash",
                    "notes": bad,
                }
            )

    supp = SupplierPaymentCreate.model_validate(
        {
            "supplier_id": "s1",
            "amount": 10,
            "payment_method": "bank_transfer",
            "reference": "AP-55",
            "notes": "Wire sent",
        }
    )
    assert supp.reference == "AP-55"
    assert supp.notes == "Wire sent"
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {
                "supplier_id": "s1",
                "amount": 10,
                "payment_method": "bank_transfer",
                "reference": "",
            }
        )
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {
                "supplier_id": "s1",
                "amount": 10,
                "payment_method": "bank_transfer",
                "notes": "!!!",
            }
        )


def test_payment_reference_notes_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Payment reference"' in page
    assert 'aria-label="Payment notes"' in page
    assert 'aria-label="Record payment"' in page
    assert "payReference.trim() || null" in page
    assert "payNotes.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Payment reference OpenAPI" in agents
    assert "Payment notes OpenAPI" in agents
    assert "PaymentReferenceValue" in agents
    assert "PaymentNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PaymentReferenceValue" in docs
    assert "PaymentNotesValue" in docs
    assert "Payment reference" in docs
    assert "Payment notes" in docs


@pytest.mark.asyncio
async def test_payment_reference_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Pay Tip Cust {uuid4().hex[:6]}"},
    )
    assert cust.status_code == 200, cust.text
    cust_id = cust.json()["data"]["id"]

    for field, bad in (
        ("reference", ""),
        ("reference", "!!!"),
        ("reference", "http://evil"),
        ("notes", ""),
        ("notes", "!!!"),
        ("notes", "http://evil"),
    ):
        resp = await ac.post(
            f"/api/v1/customers/{cust_id}/payments",
            headers=admin,
            json={
                "customer_id": cust_id,
                "amount": 1,
                "payment_method": "cash",
                field: bad,
                "apply_early_discount": False,
            },
        )
        assert resp.status_code == 422, (field, bad, resp.text)

    ok_ref = f"REF-{uuid4().hex[:8].upper()}"
    ok_notes = f"Tip173 notes {uuid4().hex[:6]}"
    ok = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cash",
            "reference": ok_ref,
            "notes": ok_notes,
            "apply_early_discount": False,
        },
    )
    assert ok.status_code == 200, ok.text
    # Create response omits reference/notes; confirm via customer history.
    hist = await ac.get(f"/api/v1/customers/{cust_id}/history", headers=admin)
    assert hist.status_code == 200, hist.text
    pay_rows = hist.json()["data"].get("payments") or []
    assert any(p.get("reference") == ok_ref for p in pay_rows), pay_rows

    omit = await ac.post(
        f"/api/v1/customers/{cust_id}/payments",
        headers=admin,
        json={
            "customer_id": cust_id,
            "amount": 1,
            "payment_method": "cash",
            "apply_early_discount": False,
        },
    )
    assert omit.status_code == 200, omit.text

    supp = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Pay Tip Sup {uuid4().hex[:6]}"},
    )
    assert supp.status_code == 200, supp.text
    supp_id = supp.json()["data"]["id"]

    blank_s = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=admin,
        json={
            "supplier_id": supp_id,
            "amount": 1,
            "payment_method": "bank_transfer",
            "reference": "",
            "apply_early_discount": False,
        },
    )
    assert blank_s.status_code == 422, blank_s.text

    notes_s = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=admin,
        json={
            "supplier_id": supp_id,
            "amount": 1,
            "payment_method": "bank_transfer",
            "notes": "!!!",
            "apply_early_discount": False,
        },
    )
    assert notes_s.status_code == 422, notes_s.text

    ok_s = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=admin,
        json={
            "supplier_id": supp_id,
            "amount": 1,
            "payment_method": "bank_transfer",
            "reference": f"AP-{uuid4().hex[:6].upper()}",
            "notes": f"Tip173 AP {uuid4().hex[:6]}",
            "apply_early_discount": False,
        },
    )
    assert ok_s.status_code == 200, ok_s.text
