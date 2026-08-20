"""Nested AiLowStockPredictionLine OpenAPI honesty (BR-21.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiLowStockPredictionLine, AiLowStockPredictionRequestsBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_low_stock_prediction_line_schema_forbid():
    ok = AiLowStockPredictionLine.model_validate(
        {
            "product_id": "  p1  ",
            "confidence": 0.8,
            "suggested_order_qty": 2,
            "risk_reason": "  low  ",
        }
    )
    assert ok.product_id == "p1"
    assert ok.confidence == 0.8
    assert ok.suggested_order_qty == 2
    assert ok.risk_reason == "low"

    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate({"product_id": ""})
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate({"product_id": "   "})
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate({})
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate(
            {"product_id": "p1", "sku": "ABC", "confidence": 0.5}
        )
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate(
            {"product_id": "p1", "confidence": "nope"}
        )
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate(
            {"product_id": "p1", "suggested_order_qty": -1}
        )
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate(
            {"product_id": "p1", "confidence": 1.5}
        )

    wrapped = AiLowStockPredictionRequestsBody.model_validate(
        {
            "lines": [
                {
                    "product_id": "p1",
                    "confidence": 0.9,
                    "suggested_order_qty": 3,
                }
            ]
        }
    )
    assert len(wrapped.lines or []) == 1
    assert isinstance(wrapped.lines[0], AiLowStockPredictionLine)

    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate(
            {"lines": [{"product_id": "p1", "seasonality": 1}]}
        )


def test_ai_low_stock_prediction_line_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "suggested_order_qty: x.suggested_order_qty" in page
    assert "predictionRiskReason.trim()" in page or "risk_reason:" in page
    assert 'aria-label="Create draft purchase requests from predictions"' in page
    assert 'aria-label="AI prediction risk reason"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI low-stock prediction line OpenAPI" in agents
    assert "AiLowStockPredictionLine" in agents
    assert "AiPredictionRiskReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiLowStockPredictionLine" in docs
    assert "extra=forbid" in docs
    assert "AiPredictionRiskReasonValue" in docs


@pytest.mark.asyncio
async def test_ai_low_stock_prediction_line_api_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    unknown_line_key = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={
            "notes": "AiLowStockPredictionLine hello-world",
            "lines": [
                {
                    "product_id": seed["p1"].id,
                    "confidence": 0.9,
                    "suggested_order_qty": 2,
                    "sku": "SHOULD_422",
                }
            ],
        },
    )
    assert unknown_line_key.status_code == 422, unknown_line_key.text

    blank_pid = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"lines": [{"product_id": "", "suggested_order_qty": 2}]},
    )
    assert blank_pid.status_code == 422, blank_pid.text

    bad_qty = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"lines": [{"product_id": seed["p1"].id, "suggested_order_qty": -3}]},
    )
    assert bad_qty.status_code == 422, bad_qty.text

    ok = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={
            "days_ahead": 14,
            "min_confidence": 0,
            "notes": "AiLowStockPredictionLine hello-world",
            "include_open": True,
            "lines": [
                {
                    "product_id": seed["p1"].id,
                    "confidence": 0.95,
                    "suggested_order_qty": 4,
                    "risk_reason": "hello-world-line",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert "created_count" in data
    assert data["created_count"] >= 1
