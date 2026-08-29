"""PurchaseOrderItemCreate.unit_id ∈ UuidIdValue OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseOrderCreate, PurchaseOrderItemCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_SUPPLIER = "22222222-3333-4444-5555-666666666666"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_po_line_unit_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseOrderItemCreate.model_validate(
        {
            "product_id": _PRODUCT,
            "quantity": 1,
            "unit_price": 1,
            "unit_id": f"  {_VALID}  ",
        }
    )
    assert ok.unit_id == _VALID.lower()
    omit_ok = PurchaseOrderItemCreate.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "unit_price": 1}
    )
    assert omit_ok.unit_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "uom_002", "a b"):
        with pytest.raises(ValidationError):
            PurchaseOrderItemCreate.model_validate(
                {
                    "product_id": _PRODUCT,
                    "quantity": 1,
                    "unit_price": 1,
                    "unit_id": bad,
                }
            )
    wrapped = PurchaseOrderCreate.model_validate(
        {
            "supplier_id": _SUPPLIER,
            "items": [
                {
                    "product_id": _PRODUCT,
                    "quantity": 1,
                    "unit_price": 1,
                    "unit_id": _VALID,
                }
            ],
        }
    )
    assert wrapped.items[0].unit_id == _VALID.lower()


def test_po_line_unit_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO unit"' in page
    assert "unit_id: unitId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO line unit_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PO unit" in docs
    assert "unit_id" in docs


@pytest.mark.asyncio
async def test_po_line_unit_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"TIP363 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "uom_002"):
        resp = await ac.post(
            "/api/v1/purchasing/orders",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": 1,
                        "unit_price": 1,
                        "unit_id": bad,
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "unit_price": 1,
                    "unit_id": f"  {str(uuid4()).upper()}  ",
                }
            ],
        },
    )
    # OpenAPI accepts a UUID; existence lookup only runs when product.unit_id is set
    # (to_stock_qty early-returns otherwise and may persist the entered id).
    assert missing.status_code in (200, 400, 404), missing.text
    assert missing.status_code != 422
