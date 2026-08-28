"""GrnItemCreate.po_item_id ∈ UuidIdValue OpenAPI honesty (BR-6.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import GrnItemCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"


def test_grn_item_po_item_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = GrnItemCreate.model_validate(
        {"po_item_id": f"  {_VALID}  ", "received_qty": 1}
    )
    assert ok.po_item_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "poi-1", "x"):
        with pytest.raises(ValidationError):
            GrnItemCreate.model_validate({"po_item_id": bad, "received_qty": 1})
    with pytest.raises(ValidationError):
        GrnItemCreate.model_validate({"received_qty": 1})


def test_grn_item_po_item_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "po_item_id: String(i.id).trim()" in page
    assert 'aria-label="Post GRN"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GRN item po_item_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "po_item_id" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_grn_item_po_item_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP380 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip380-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": product_id, "quantity": 2, "unit_price": 1}],
        },
    )
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    sent = await ac.post(
        f"/api/v1/purchasing/orders/{po_data['id']}/send?to=tip380@example.com",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "poi-1"):
        resp = await ac.post(
            "/api/v1/purchasing/grn",
            headers=headers,
            json={
                "purchase_order_id": po_data["id"],
                "items": [{"po_item_id": bad, "received_qty": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_data["id"],
            "items": [
                {
                    "po_item_id": f"  {str(uuid4()).upper()}  ",
                    "received_qty": 1,
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
