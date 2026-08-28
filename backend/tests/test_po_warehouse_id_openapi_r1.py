"""PurchaseOrderCreate.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseOrderCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_SUPPLIER = "22222222-3333-4444-5555-666666666666"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_ITEMS = [{"product_id": _PRODUCT, "quantity": 1, "unit_price": 1}]


def test_po_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseOrderCreate.model_validate(
        {
            "supplier_id": _SUPPLIER,
            "warehouse_id": f"  {_VALID}  ",
            "items": _ITEMS,
        }
    )
    assert ok.warehouse_id == _VALID.lower()
    omit_ok = PurchaseOrderCreate.model_validate(
        {"supplier_id": _SUPPLIER, "items": _ITEMS}
    )
    assert omit_ok.warehouse_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            PurchaseOrderCreate.model_validate(
                {
                    "supplier_id": _SUPPLIER,
                    "warehouse_id": bad,
                    "items": _ITEMS,
                }
            )


def test_po_warehouse_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "warehouse_id" in docs
    assert "POST /purchasing/orders" in docs
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO supplier"' in page


@pytest.mark.asyncio
async def test_po_warehouse_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"TIP362 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    item = {"product_id": product_id, "quantity": 1, "unit_price": 1}

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            "/api/v1/purchasing/orders",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "warehouse_id": bad,
                "items": [item],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
