"""AiLowStockPredictionLine.preferred_supplier_id ∈ UuidIdValue OpenAPI honesty (BR-21.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiLowStockPredictionLine, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_ai_prediction_line_preferred_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = AiLowStockPredictionLine.model_validate(
        {
            "product_id": _PRODUCT,
            "preferred_supplier_id": f"  {_VALID}  ",
            "suggested_order_qty": 1,
        }
    )
    assert ok.preferred_supplier_id == _VALID.lower()
    omit_ok = AiLowStockPredictionLine.model_validate({"product_id": _PRODUCT})
    assert omit_ok.preferred_supplier_id is None
    nullish = AiLowStockPredictionLine.model_validate(
        {"product_id": _PRODUCT, "preferred_supplier_id": None}
    )
    assert nullish.preferred_supplier_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "sup_002", "a b"):
        with pytest.raises(ValidationError):
            AiLowStockPredictionLine.model_validate(
                {"product_id": _PRODUCT, "preferred_supplier_id": bad}
            )


def test_ai_prediction_line_preferred_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "preferred_supplier_id: x.preferred_supplier_id" in page
    assert "String(x.preferred_supplier_id).trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI low-stock prediction line preferred_supplier_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "preferred_supplier_id" in docs
    assert "AiLowStockPredictionLine" in docs


@pytest.mark.asyncio
async def test_ai_prediction_line_preferred_supplier_id_api_blank_invalid_422(
    client, seeded
):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_002"):
        resp = await ac.post(
            "/api/v1/ai/inventory/low-stock-prediction/requests",
            headers=headers,
            json={
                "lines": [
                    {
                        "product_id": product_id,
                        "suggested_order_qty": 1,
                        "preferred_supplier_id": bad,
                    }
                ]
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={
            "include_open": True,
            "lines": [
                {
                    "product_id": product_id,
                    "suggested_order_qty": 1,
                    "preferred_supplier_id": f"  {str(uuid4()).upper()}  ",
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
