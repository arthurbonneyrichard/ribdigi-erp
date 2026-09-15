"""GrnCreate.purchase_order_id ∈ UuidIdValue OpenAPI honesty (BR-6.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import GrnCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEM = {
    "po_item_id": "BBBBBBBB-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
    "received_qty": 1,
    "accepted_qty": 1,
    "rejected_qty": 0,
}


def test_grn_purchase_order_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = GrnCreate.model_validate(
        {"purchase_order_id": f"  {_VALID}  ", "items": [_ITEM]}
    )
    assert ok.purchase_order_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "po_001", "a b"):
        with pytest.raises(ValidationError):
            GrnCreate.model_validate({"purchase_order_id": bad, "items": [_ITEM]})
    with pytest.raises(ValidationError):
        GrnCreate.model_validate({"items": [_ITEM]})


def test_grn_purchase_order_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="GRN purchase order"' in page
    assert "purchase_order_id: String(po.id).trim()" in page
    assert 'aria-label="Post GRN"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GRN purchase_order_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "GRN purchase order" in docs
    assert "POST /purchases/grn" in docs or "POST /purchasing/grn" in docs


@pytest.mark.asyncio
async def test_grn_purchase_order_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "po_001"):
        resp = await ac.post(
            "/api/v1/purchasing/grn",
            headers=headers,
            json={
                "purchase_order_id": bad,
                "items": [
                    {
                        "po_item_id": str(uuid4()),
                        "received_qty": 1,
                        "accepted_qty": 1,
                        "rejected_qty": 0,
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "items": [
                {
                    "po_item_id": str(uuid4()),
                    "received_qty": 1,
                    "accepted_qty": 1,
                    "rejected_qty": 0,
                }
            ]
        },
    )
    assert omit.status_code == 422, omit.text

    missing = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": str(uuid4()),
            "items": [
                {
                    "po_item_id": str(uuid4()),
                    "received_qty": 1,
                    "accepted_qty": 1,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
