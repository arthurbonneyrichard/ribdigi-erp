"""AiLowStockPredictionLine.product_id ∈ UuidIdValue OpenAPI honesty (BR-21.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiLowStockPredictionLine, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_prediction_line_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = AiLowStockPredictionLine.model_validate(
        {"product_id": f"  {_VALID}  ", "suggested_order_qty": 1}
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "prod_001", "a b", "p1"):
        with pytest.raises(ValidationError):
            AiLowStockPredictionLine.model_validate({"product_id": bad})
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate({})


def test_ai_prediction_line_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "product_id: String(x.product_id || '').trim()" in page
    assert 'aria-label="Create draft purchase requests from predictions"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI low-stock prediction line product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiLowStockPredictionLine" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_ai_prediction_line_product_id_api_blank_invalid_422(client, seeded):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.post(
            "/api/v1/ai/inventory/low-stock-prediction/requests",
            headers=headers,
            json={"lines": [{"product_id": bad, "suggested_order_qty": 1}]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={
            "include_open": True,
            "lines": [
                {
                    "product_id": f"  {str(uuid4()).upper()}  ",
                    "suggested_order_qty": 1,
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
