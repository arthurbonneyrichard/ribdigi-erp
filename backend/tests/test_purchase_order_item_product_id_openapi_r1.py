"""PurchaseOrderItemCreate.product_id ∈ UuidIdValue OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseOrderItemCreate, PurchaseOrderCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_SUPPLIER = "11111111-2222-3333-4444-555555555555"
_LINE = {"quantity": 1, "unit_price": 10}


def test_purchase_order_item_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseOrderItemCreate.model_validate({**_LINE, "product_id": f"  {_VALID}  "})
    assert ok.product_id == _VALID.lower()
    po = PurchaseOrderCreate.model_validate(
        {"supplier_id": _SUPPLIER, "items": [{**_LINE, "product_id": _VALID}]}
    )
    assert po.items[0].product_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "prod_001", "p1"):
        with pytest.raises(ValidationError):
            PurchaseOrderItemCreate.model_validate({**_LINE, "product_id": bad})
    with pytest.raises(ValidationError):
        PurchaseOrderItemCreate.model_validate(_LINE)


def test_purchase_order_item_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO product"' in page
    assert "product_id: productId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO line product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PO product" in docs
    assert "Each line requires `product_id`" in docs


@pytest.mark.asyncio
async def test_purchase_order_item_product_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"Tip294 Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "p1", "prod_001"):
        resp = await ac.post(
            "/api/v1/purchasing/orders",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "items": [{"product_id": bad, "quantity": 1, "unit_price": 5}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={"supplier_id": supplier_id, "items": [{"quantity": 1, "unit_price": 5}]},
    )
    assert omit.status_code == 422, omit.text

    ok = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": f"  {str(seed['p1'].id).upper()}  ",
                    "quantity": 2,
                    "unit_price": 3.5,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text

    missing = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": str(uuid4()), "quantity": 1, "unit_price": 1}],
        },
    )
    assert missing.status_code in (400, 404), missing.text
