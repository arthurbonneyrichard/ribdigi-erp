"""POST /ai/inventory/low-stock-prediction/requests typed body OpenAPI (BR-21.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiLowStockPredictionRequestsBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_low_stock_requests_body_schema_forbid():
    bare = AiLowStockPredictionRequestsBody.model_validate({})
    assert bare.days_ahead == 14
    assert bare.min_confidence == 0
    assert bare.include_open is False
    assert bare.lines is None

    ok = AiLowStockPredictionRequestsBody.model_validate(
        {
            "days_ahead": 30,
            "min_confidence": 0.5,
            "notes": "  hello  ",
            "include_open": True,
            "lines": [{"product_id": "p1", "confidence": 0.9, "suggested_order_qty": 2}],
        }
    )
    assert ok.days_ahead == 30
    assert ok.min_confidence == 0.5
    assert ok.notes == "hello"
    assert ok.include_open is True
    assert len(ok.lines or []) == 1

    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"days_ahead": 14, "extra": True})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"days_ahead": 0})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"days_ahead": 999})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"days_ahead": ""})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"days_ahead": "abc"})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"min_confidence": -0.1})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"min_confidence": 1.5})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"min_confidence": "nope"})


def test_ai_low_stock_requests_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create draft purchase requests from predictions"' in page
    assert 'aria-label="Include open purchase requests"' in page
    assert 'aria-label="AI low-stock prediction notes"' in page
    assert "AiLowStockPredictionLine" in page or "predictionNotes" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI low-stock prediction requests body OpenAPI" in agents
    assert "AiLowStockPredictionRequestsBody" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiLowStockPredictionRequestsBody" in docs
    assert "POST /ai/inventory/low-stock-prediction/requests" in docs
    assert "extra=forbid" in docs
    assert "AiLowStockPredictionLine" in docs


@pytest.mark.asyncio
async def test_ai_low_stock_requests_api_unknown_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"days_ahead": 14, "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    bad_days = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"days_ahead": "abc"},
    )
    assert bad_days.status_code == 422, bad_days.text

    blank_days = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"days_ahead": ""},
    )
    assert blank_days.status_code == 422, blank_days.text

    bad_conf = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"min_confidence": 2},
    )
    assert bad_conf.status_code == 422, bad_conf.text

    # Empty body still valid — re-run prediction (may create 0 PRs).
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
                    "suggested_order_qty": 3,
                    "risk_reason": "hello-world",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert "created_count" in data
    assert data["created_count"] >= 1
