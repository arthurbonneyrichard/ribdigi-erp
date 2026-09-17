"""PurchaseInvoiceCreate.supplier_id ∈ UuidIdValue OpenAPI honesty (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseInvoiceCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [
    {
        "product_id": "11111111-2222-3333-4444-555555555555",
        "quantity": 1,
        "unit_price": 1,
    }
]


def test_pi_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = PurchaseInvoiceCreate.model_validate({"items": _ITEMS})
    assert omit.supplier_id is None
    ok = PurchaseInvoiceCreate.model_validate(
        {"supplier_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.supplier_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "s1"):
        with pytest.raises(ValidationError):
            PurchaseInvoiceCreate.model_validate(
                {"supplier_id": bad, "items": _ITEMS}
            )


def test_pi_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase invoice supplier"' in page
    assert "supplier_id: manualInvSupplierId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase invoice supplier_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Purchase invoice supplier" in docs
    assert "POST /purchasing/invoices" in docs


@pytest.mark.asyncio
async def test_pi_supplier_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "s1"):
        resp = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={"supplier_id": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
