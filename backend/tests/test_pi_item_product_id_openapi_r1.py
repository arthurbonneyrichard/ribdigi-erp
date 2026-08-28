"""PurchaseInvoiceItemCreate.product_id ∈ UuidIdValue OpenAPI honesty (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseInvoiceCreate, PurchaseInvoiceItemCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_SUP = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_pi_item_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseInvoiceItemCreate.model_validate(
        {"product_id": f"  {_VALID}  ", "quantity": 1, "unit_price": 1}
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "p1"):
        with pytest.raises(ValidationError):
            PurchaseInvoiceItemCreate.model_validate(
                {"product_id": bad, "quantity": 1, "unit_price": 1}
            )
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate(
            {
                "supplier_id": _SUP,
                "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
            }
        )


def test_pi_item_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase invoice product"' in page
    assert "product_id: manualInvProductId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase invoice item product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Purchase invoice product" in docs
    assert "items[].product_id" in docs


@pytest.mark.asyncio
async def test_pi_item_product_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP391 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip391-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "p1"):
        resp = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "items": [{"product_id": bad, "quantity": 1, "unit_price": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": f"  {str(uuid4()).upper()}  ",
                    "quantity": 1,
                    "unit_price": 1,
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
