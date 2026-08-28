"""PurchaseReturnItemCreate.goods_receipt_item_id ∈ UuidIdValue OpenAPI honesty (BR-6.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseReturnCreate, PurchaseReturnItemCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_GRN = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_pr_item_goods_receipt_item_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseReturnItemCreate.model_validate(
        {"goods_receipt_item_id": f"  {_VALID}  ", "quantity": 1}
    )
    assert ok.goods_receipt_item_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "gi-1", "i1"):
        with pytest.raises(ValidationError):
            PurchaseReturnItemCreate.model_validate(
                {"goods_receipt_item_id": bad, "quantity": 1}
            )
    with pytest.raises(ValidationError):
        PurchaseReturnCreate.model_validate(
            {
                "goods_receipt_id": _GRN,
                "reason": "damaged",
                "items": [{"goods_receipt_item_id": "gi-1", "quantity": 1}],
            }
        )


def test_pr_item_goods_receipt_item_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase return GRN line"' in page
    assert "goods_receipt_item_id: grnItemId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase return item goods_receipt_item_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "goods_receipt_item_id" in docs
    assert "Purchase return GRN line" in docs


@pytest.mark.asyncio
async def test_pr_item_goods_receipt_item_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP381 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip381-{suffix}@example.com",
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
        f"/api/v1/purchasing/orders/{po_data['id']}/send?to=tip381@example.com",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_data["id"],
            "items": [
                {
                    "po_item_id": po_data["items"][0]["id"],
                    "received_qty": 2,
                    "accepted_qty": 2,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "gi-1"):
        resp = await ac.post(
            "/api/v1/purchasing/returns",
            headers=headers,
            json={
                "goods_receipt_id": grn_id,
                "reason": "damaged",
                "items": [{"goods_receipt_item_id": bad, "quantity": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers,
        json={
            "goods_receipt_id": grn_id,
            "reason": "damaged",
            "items": [
                {
                    "goods_receipt_item_id": f"  {str(uuid4()).upper()}  ",
                    "quantity": 1,
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
