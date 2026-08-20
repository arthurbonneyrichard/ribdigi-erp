"""AiLowStockPredictionRequestsBody / line notes OpenAPI honesty (BR-21.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import AiLowStockPredictionLine, AiLowStockPredictionRequestsBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_low_stock_prediction_notes_schema():
    omit = AiLowStockPredictionRequestsBody.model_validate({})
    assert omit.notes is None
    ok = AiLowStockPredictionRequestsBody.model_validate(
        {"notes": "  Restock from prediction  "}
    )
    assert ok.notes == "Restock from prediction"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            AiLowStockPredictionRequestsBody.model_validate({"notes": bad})

    line_ok = AiLowStockPredictionLine.model_validate(
        {"product_id": "p1", "notes": "  Line urgent  "}
    )
    assert line_ok.notes == "Line urgent"
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate({"product_id": "p1", "notes": "!!!!"})


def test_ai_low_stock_prediction_notes_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI low-stock prediction notes"' in page
    assert "predictionNotes.trim() || null" in page
    assert 'aria-label="Create draft purchase requests from predictions"' in page
    assert 'aria-label="Inventory predictions"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseRequestNotesValue" in agents
    assert "AiLowStockPredictionRequestsBody" in agents
    assert "AI low-stock prediction notes" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseRequestNotesValue" in docs
    assert "AI low-stock prediction notes" in docs


@pytest.mark.asyncio
async def test_ai_low_stock_prediction_notes_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP186 notes {suffix}"
    item = {
        "product_id": seed["p1"].id,
        "suggested_order_qty": 2,
        "confidence": 0.9,
    }

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/ai/inventory/low-stock-prediction/requests",
            headers=headers,
            json={"notes": bad, "lines": [item], "include_open": True},
        )
        assert resp.status_code == 422, (bad, resp.text)

    bad_line = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={
            "include_open": True,
            "lines": [{**item, "notes": "!!!!"}],
        },
    )
    assert bad_line.status_code == 422, bad_line.text

    ok = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"notes": f"  {tag}  ", "lines": [item], "include_open": True},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json().get("data") or {}
    created = data.get("created") or []
    assert created, ok.json()
    notes_hit = [c for c in created if tag in str(c.get("notes") or "")]
    assert notes_hit, ok.json()
