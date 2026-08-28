"""GrnCreate.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-6.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import GrnCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PO = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_PO_ITEM = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
_ITEMS = [{"po_item_id": _PO_ITEM, "received_qty": 1}]


def test_grn_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = GrnCreate.model_validate(
        {
            "purchase_order_id": _PO,
            "warehouse_id": f"  {_VALID}  ",
            "items": _ITEMS,
        }
    )
    assert ok.warehouse_id == _VALID.lower()
    omit_ok = GrnCreate.model_validate({"purchase_order_id": _PO, "items": _ITEMS})
    assert omit_ok.warehouse_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            GrnCreate.model_validate(
                {
                    "purchase_order_id": _PO,
                    "warehouse_id": bad,
                    "items": _ITEMS,
                }
            )


def test_grn_warehouse_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GRN warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "warehouse_id" in docs
    assert "grn" in docs.lower()
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Post GRN"' in page


@pytest.mark.asyncio
async def test_grn_warehouse_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP366 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip366-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {"product_id": product_id, "quantity": 2, "unit_price": 1},
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    sent = await ac.post(
        f"/api/v1/purchasing/orders/{po_data['id']}/send?to=tip366@example.com",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    po_item_id = po_data["items"][0]["id"]
    item = {"po_item_id": po_item_id, "received_qty": 1}

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            "/api/v1/purchasing/grn",
            headers=headers,
            json={
                "purchase_order_id": po_data["id"],
                "warehouse_id": bad,
                "items": [item],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_data["id"],
            "warehouse_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
