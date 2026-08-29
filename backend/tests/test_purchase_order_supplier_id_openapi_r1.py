"""PurchaseOrderCreate.supplier_id ∈ UuidIdValue OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseOrderCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_PROD = "11111111-2222-3333-4444-555555555555"
_ITEMS = [{"product_id": _PROD, "quantity": 1, "unit_price": 10}]


def test_purchase_order_supplier_id_schema():
    ok = PurchaseOrderCreate.model_validate(
        {"supplier_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.supplier_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_001"):
        with pytest.raises(ValidationError):
            PurchaseOrderCreate.model_validate({"supplier_id": bad, "items": _ITEMS})
    with pytest.raises(ValidationError):
        PurchaseOrderCreate.model_validate({"items": _ITEMS})


def test_purchase_order_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO supplier"' in page
    assert "supplier_id: supplierId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase order supplier_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "PO supplier" in docs


@pytest.mark.asyncio
async def test_purchase_order_supplier_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4.5}

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"Tip261 Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_001"):
        resp = await ac.post(
            "/api/v1/purchasing/orders",
            headers=headers,
            json={"supplier_id": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={"items": [item]},
    )
    assert omit.status_code == 422, omit.text

    ok = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={"supplier_id": f"  {str(supplier_id).upper()}  ", "items": [item]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["supplier_id"] == str(supplier_id).lower()

    missing = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={"supplier_id": str(uuid4()), "items": [item]},
    )
    assert missing.status_code in (400, 404), missing.text
