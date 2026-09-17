"""CustomerPaymentCreate.liquid_account_id ∈ UuidIdValue OpenAPI honesty (BR-11.1)."""

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
_CUST = "11111111-2222-3333-4444-555555555555"


def test_customer_payment_liquid_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = CustomerPaymentCreate.model_validate({"customer_id": _CUST, "amount": 1})
    assert omit.liquid_account_id is None
    ok = CustomerPaymentCreate.model_validate(
        {"customer_id": _CUST, "amount": 1, "liquid_account_id": f"  {_VALID}  "}
    )
    assert ok.liquid_account_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        with pytest.raises(ValidationError):
            CustomerPaymentCreate.model_validate(
                {"customer_id": _CUST, "amount": 1, "liquid_account_id": bad}
            )


def test_customer_payment_liquid_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Credit payment liquid account"' in page
    assert "liquid_account_id: liquidAccountId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Customer payment liquid_account_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Credit payment liquid account" in docs


@pytest.mark.asyncio
async def test_customer_payment_liquid_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cust = seed["party1"].id
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            f"/api/v1/customers/{cust}/payments",
            headers=headers,
            json={"customer_id": cust, "amount": 1, "liquid_account_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/customers/{cust}/payments",
        headers=headers,
        json={
            "customer_id": cust,
            "amount": 1,
            "liquid_account_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
