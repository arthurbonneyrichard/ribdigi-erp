"""CustomerPaymentCreate.customer_id ∈ UuidIdValue OpenAPI honesty (BR-11)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CustomerPaymentCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_customer_payment_customer_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = CustomerPaymentCreate.model_validate(
        {"customer_id": f"  {_VALID}  ", "amount": 10}
    )
    assert ok.customer_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        with pytest.raises(ValidationError):
            CustomerPaymentCreate.model_validate({"customer_id": bad, "amount": 10})
    with pytest.raises(ValidationError):
        CustomerPaymentCreate.model_validate({"amount": 10})


def test_customer_payment_customer_id_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Credit payment party"' in page
    assert "customer_id: partyId.trim()" in page
    assert 'aria-label="Record payment"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Customer payment customer_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "Credit payment party" in docs
    assert "POST /customers/{customer_id}/payments" in docs


@pytest.mark.asyncio
async def test_customer_payment_customer_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cust = seed["party1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        resp = await ac.post(
            f"/api/v1/customers/{cust}/payments",
            headers=headers,
            json={"customer_id": bad, "amount": 1},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        f"/api/v1/customers/{cust}/payments",
        headers=headers,
        json={"amount": 1},
    )
    assert omit.status_code == 422, omit.text

    # Well-formed UUID (trimmed/lowered by schema) must not 422; business outcome varies.
    shaped = await ac.post(
        f"/api/v1/customers/{cust}/payments",
        headers=headers,
        json={"customer_id": f"  {str(cust).upper()}  ", "amount": 0.01},
    )
    assert shaped.status_code != 422, shaped.text
    if shaped.status_code == 200:
        assert shaped.json()["data"]["customer_id"] == str(cust).lower()

    missing = await ac.post(
        f"/api/v1/customers/{uuid4()}/payments",
        headers=headers,
        json={"customer_id": str(uuid4()), "amount": 1},
    )
    assert missing.status_code in (400, 404), missing.text
