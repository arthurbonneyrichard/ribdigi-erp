"""StockMove.unit_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockMove, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_stock_move_unit_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = StockMove.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "unit_id": f"  {_VALID}  "}
    )
    assert ok.unit_id == _VALID.lower()
    omit = StockMove.model_validate({"product_id": _PRODUCT, "quantity": 1})
    assert omit.unit_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "uom_002"):
        with pytest.raises(ValidationError):
            StockMove.model_validate(
                {"product_id": _PRODUCT, "quantity": 1, "unit_id": bad}
            )


def test_stock_move_unit_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in unit"' in page
    assert "unit_id: stockUnitId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock-in unit_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stock-in unit" in docs


@pytest.mark.asyncio
async def test_stock_move_unit_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "uom_002"):
        resp = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": product_id, "quantity": 1, "unit_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)
    missing = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "unit_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (200, 400, 404), missing.text
    assert missing.status_code != 422
