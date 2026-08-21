"""SupplierPaymentCreate.supplier_id ∈ UuidIdValue OpenAPI honesty (BR-11.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SupplierPaymentCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_supplier_payment_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = SupplierPaymentCreate.model_validate(
        {"supplier_id": f"  {_VALID}  ", "amount": 10}
    )
    assert ok.supplier_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "supp_001"):
        with pytest.raises(ValidationError):
            SupplierPaymentCreate.model_validate({"supplier_id": bad, "amount": 10})
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate({"amount": 10})


def test_supplier_payment_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Credit payment party"' in page
    assert "supplier_id: partyId.trim()" in page
    assert 'aria-label="Record payment"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Supplier payment supplier_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "Credit payment party" in docs
    assert "POST /suppliers/{supplier_id}/payments" in docs
    assert "required body `supplier_id` ∈ `UuidIdValue`" in docs


@pytest.mark.asyncio
async def test_supplier_payment_supplier_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    supp = seed.get("supplier1") or seed.get("party_supplier") or seed.get("supp1")
    if supp is None:
        listed = await ac.get("/api/v1/suppliers", headers=headers)
        assert listed.status_code == 200, listed.text
        rows = listed.json().get("data") or []
        assert rows, "seeded supplier required"
        supp_id = rows[0]["id"]
    else:
        supp_id = getattr(supp, "id", None) or supp["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "supp_001"):
        resp = await ac.post(
            f"/api/v1/suppliers/{supp_id}/payments",
            headers=headers,
            json={"supplier_id": bad, "amount": 1},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=headers,
        json={"amount": 1},
    )
    assert omit.status_code == 422, omit.text

    shaped = await ac.post(
        f"/api/v1/suppliers/{supp_id}/payments",
        headers=headers,
        json={"supplier_id": f"  {str(supp_id).upper()}  ", "amount": 0.01},
    )
    assert shaped.status_code != 422, shaped.text
    if shaped.status_code == 200:
        assert shaped.json()["data"]["supplier_id"] == str(supp_id).lower()

    missing = await ac.post(
        f"/api/v1/suppliers/{uuid4()}/payments",
        headers=headers,
        json={"supplier_id": str(uuid4()), "amount": 1},
    )
    assert missing.status_code in (400, 404), missing.text
