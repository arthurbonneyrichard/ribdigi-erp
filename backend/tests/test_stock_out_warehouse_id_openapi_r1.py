"""StockOut.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockOut, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_PRODUCT = "11111111-2222-3333-4444-555555555555"
_BASE = {"product_id": _PRODUCT, "quantity": 1, "reference_type": "sale"}


def test_stock_out_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = StockOut.model_validate(_BASE)
    assert omit.warehouse_id is None
    ok = StockOut.model_validate({**_BASE, "warehouse_id": f"  {_VALID}  "})
    assert ok.warehouse_id == _VALID.lower()
    nullish = StockOut.model_validate({**_BASE, "warehouse_id": None})
    assert nullish.warehouse_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            StockOut.model_validate({**_BASE, "warehouse_id": bad})


def test_stock_out_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-out warehouse"' in page
    assert "warehouse_id: outWarehouseId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "StockOut warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stock-out warehouse" in docs
    assert "POST /inventory/stock-out" in docs


@pytest.mark.asyncio
async def test_stock_out_warehouse_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            "/api/v1/inventory/stock-out",
            headers=headers,
            json={
                "product_id": product_id,
                "quantity": 1,
                "reference_type": "sale",
                "warehouse_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "reference_type": "sale",
        },
    )
    assert omit.status_code in (200, 400), omit.text

    missing = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "reference_type": "sale",
            "warehouse_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
