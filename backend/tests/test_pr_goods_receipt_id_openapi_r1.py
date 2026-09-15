"""PurchaseReturnCreate.goods_receipt_id ∈ UuidIdValue OpenAPI honesty (BR-6.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseReturnCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [
    {
        "goods_receipt_item_id": "11111111-2222-3333-4444-555555555555",
        "quantity": 1,
    }
]


def test_pr_goods_receipt_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = PurchaseReturnCreate.model_validate(
        {
            "goods_receipt_id": f"  {_VALID}  ",
            "reason": "damaged",
            "items": _ITEMS,
        }
    )
    assert ok.goods_receipt_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "grn_001", "a b"):
        with pytest.raises(ValidationError):
            PurchaseReturnCreate.model_validate(
                {"goods_receipt_id": bad, "reason": "damaged", "items": _ITEMS}
            )
    with pytest.raises(ValidationError):
        PurchaseReturnCreate.model_validate({"reason": "damaged", "items": _ITEMS})


def test_pr_goods_receipt_id_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Return from GRN"' in page
    assert "goods_receipt_id: grnId.trim()" in page
    assert 'aria-label="Create purchase return"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase return goods_receipt_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /purchasing/returns" in docs
    assert "Return from GRN" in docs


@pytest.mark.asyncio
async def test_pr_goods_receipt_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {
        "goods_receipt_item_id": str(uuid4()),
        "quantity": 1,
    }

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "grn_001"):
        resp = await ac.post(
            "/api/v1/purchasing/returns",
            headers=headers,
            json={"goods_receipt_id": bad, "reason": "damaged", "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers,
        json={"reason": "damaged", "items": [item]},
    )
    assert omit.status_code == 422, omit.text

    missing = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers,
        json={
            "goods_receipt_id": f"  {str(uuid4()).upper()}  ",
            "reason": "damaged",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
