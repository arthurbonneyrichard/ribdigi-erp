"""SupplierPaymentCreate.purchase_order_id ∈ UuidIdValue OpenAPI honesty (BR-11.2)."""

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
_SUP = "11111111-2222-3333-4444-555555555555"


def test_supplier_payment_po_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = SupplierPaymentCreate.model_validate({"supplier_id": _SUP, "amount": 1})
    assert omit.purchase_order_id is None
    ok = SupplierPaymentCreate.model_validate(
        {"supplier_id": _SUP, "amount": 1, "purchase_order_id": f"  {_VALID}  "}
    )
    assert ok.purchase_order_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "po_001"):
        with pytest.raises(ValidationError):
            SupplierPaymentCreate.model_validate(
                {"supplier_id": _SUP, "amount": 1, "purchase_order_id": bad}
            )


def test_supplier_payment_po_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Supplier payment purchase_order_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "purchase_order_id" in docs
    assert "/suppliers/{supplier_id}/payments" in docs


@pytest.mark.asyncio
async def test_supplier_payment_po_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP394 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip394-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supp = supplier.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "po_001"):
        resp = await ac.post(
            f"/api/v1/suppliers/{supp}/payments",
            headers=headers,
            json={"supplier_id": supp, "amount": 1, "purchase_order_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/suppliers/{supp}/payments",
        headers=headers,
        json={
            "supplier_id": supp,
            "amount": 1,
            "purchase_order_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
