"""AiLowStockPredictionLine.risk_reason OpenAPI honesty (BR-21.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import AiLowStockPredictionLine, AiLowStockPredictionRequestsBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_prediction_risk_reason_schema():
    omit = AiLowStockPredictionLine.model_validate({"product_id": "p1"})
    assert omit.risk_reason is None
    ok = AiLowStockPredictionLine.model_validate(
        {"product_id": "p1", "risk_reason": "  predicted_stockout  "}
    )
    assert ok.risk_reason == "predicted_stockout"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            AiLowStockPredictionLine.model_validate(
                {"product_id": "p1", "risk_reason": bad}
            )

    wrapped = AiLowStockPredictionRequestsBody.model_validate(
        {
            "lines": [
                {
                    "product_id": "p1",
                    "suggested_order_qty": 2,
                    "risk_reason": "below_reorder",
                }
            ]
        }
    )
    assert wrapped.lines[0].risk_reason == "below_reorder"


def test_ai_prediction_risk_reason_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI prediction risk reason"' in page
    assert "predictionRiskReason.trim()" in page
    assert 'aria-label="Create draft purchase requests from predictions"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AiPredictionRiskReasonValue" in agents
    assert "AI prediction risk reason" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiPredictionRiskReasonValue" in docs
    assert "AI prediction risk reason" in docs


@pytest.mark.asyncio
async def test_ai_prediction_risk_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP188 risk {suffix}"
    base = {
        "product_id": seed["p1"].id,
        "suggested_order_qty": 2,
        "confidence": 0.9,
    }

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/ai/inventory/low-stock-prediction/requests",
            headers=headers,
            json={
                "include_open": True,
                "notes": tag,
                "lines": [{**base, "risk_reason": bad}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={
            "include_open": True,
            "notes": tag,
            "lines": [{**base, "risk_reason": f"UI risk reason {suffix}"}],
        },
    )
    assert ok.status_code == 200, ok.text
    created = (ok.json().get("data") or {}).get("created") or []
    assert created, ok.text
    item_notes = (created[0].get("items") or [{}])[0].get("notes") or ""
    assert f"UI risk reason {suffix}" in item_notes
    assert created[0].get("notes") == tag
