"""StockMove.product_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockMove, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_stock_move_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = StockMove.model_validate({"product_id": f"  {_VALID}  ", "quantity": 1})
    assert ok.product_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "prod_001", "a b"):
        with pytest.raises(ValidationError):
            StockMove.model_validate({"product_id": bad, "quantity": 1})
    with pytest.raises(ValidationError):
        StockMove.model_validate({"quantity": 1})


def test_stock_move_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Selected product"' in page
    assert "product_id: selectedId.trim()" in page
    assert 'aria-label="Receive batch"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "StockMove product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /inventory/stock-in" in docs
    assert "Selected product" in docs


@pytest.mark.asyncio
async def test_stock_move_product_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": bad, "quantity": 1},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"quantity": 1},
    )
    assert omit.status_code == 422, omit.text

    missing = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": f"  {str(uuid4()).upper()}  ", "quantity": 1},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
