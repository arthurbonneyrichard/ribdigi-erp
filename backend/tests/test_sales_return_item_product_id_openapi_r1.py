"""SalesReturnItemCreate.product_id ∈ UuidIdValue OpenAPI honesty (BR-7.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SalesReturnCreate, SalesReturnItemCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_INVOICE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_sales_return_item_product_id_schema():
    ok = SalesReturnItemCreate.model_validate(
        {"product_id": f"  {_VALID}  ", "quantity": 1, "condition": "sellable"}
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001", "p1"):
        with pytest.raises(ValidationError):
            SalesReturnItemCreate.model_validate(
                {"product_id": bad, "quantity": 1, "condition": "discard"}
            )
    wrapped = SalesReturnCreate.model_validate(
        {
            "sales_invoice_id": _INVOICE,
            "reason": "damaged",
            "items": [{"product_id": _VALID, "quantity": 1, "condition": "discard"}],
        }
    )
    assert wrapped.items[0].product_id == _VALID.lower()


def test_sales_return_item_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "product_id: productId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales return item product_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "POST /sales/returns" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_sales_return_item_product_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    # Need a real invoice id shape for schema; blank product still 422 before invoice lookup.
    inv = str(uuid4())
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.post(
            "/api/v1/sales/returns",
            headers=headers,
            json={
                "sales_invoice_id": inv,
                "reason": "damaged",
                "items": [{"product_id": bad, "quantity": 1, "condition": "discard"}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)
