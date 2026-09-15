"""OpenAPI honesty tips #533–#535: UnitIntervalValue, sale totals, approval step."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AiLowStockPredictionLine,
    AiLowStockPredictionRequestsBody,
    ApprovalLevelUpdate,
    NonNegativeMoneyValue,
    PosSaleCreate,
    PurchaseApprovalLevelUpdate,
    TransactionCreate,
    UnitIntervalValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_ui = TypeAdapter(UnitIntervalValue)
_nn = TypeAdapter(NonNegativeMoneyValue)


def test_unit_interval_sale_totals_step_schema():
    assert _ui.validate_python(0) == 0.0
    assert _ui.validate_python(1) == 1.0
    assert _ui.validate_python(0.42) == 0.42
    for bad in (-0.01, 1.01, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            _ui.validate_python(bad)

    AiLowStockPredictionLine.model_validate(
        {"product_id": str(uuid4()), "confidence": 0.8}
    )
    with pytest.raises(ValidationError):
        AiLowStockPredictionLine.model_validate(
            {"product_id": str(uuid4()), "confidence": float("nan")}
        )

    AiLowStockPredictionRequestsBody.model_validate({"min_confidence": 0.3})
    with pytest.raises(ValidationError):
        AiLowStockPredictionRequestsBody.model_validate({"min_confidence": 1.5})

    PosSaleCreate.model_validate(
        {
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
            "subtotal": 10,
            "tax": 1,
            "total": 11,
        }
    )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "items": [{"product_id": str(uuid4()), "quantity": 1}],
                "tax": float("inf"),
            }
        )

    TransactionCreate.model_validate({"subtotal": 0, "tax": 0, "total": 0})
    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"subtotal": -1})

    ApprovalLevelUpdate.model_validate(
        {"min_amount": 100, "roles": ["accountant"], "step": 1}
    )
    with pytest.raises(ValidationError):
        ApprovalLevelUpdate.model_validate(
            {"min_amount": 100, "roles": ["accountant"], "step": 0}
        )
    with pytest.raises(ValidationError):
        PurchaseApprovalLevelUpdate.model_validate(
            {"roles": ["company_admin"], "step": 99}
        )


def test_unit_interval_sale_totals_step_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Unit interval confidence OpenAPI",
        "POS / legacy sale totals OpenAPI",
        "Approval matrix step OpenAPI",
    ):
        assert title in agents, title
    assert "UnitIntervalValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UnitIntervalValue" in docs
    assert "POS cart totals" in docs

    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI prediction min confidence"' in ai
    assert "body.min_confidence" in ai or "min_confidence" in ai

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS cart totals"' in pos


@pytest.mark.asyncio
async def test_unit_interval_sale_totals_step_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"min_confidence": "inf", "days_ahead": 14},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/ai/inventory/low-stock-prediction/requests",
        headers=headers,
        json={"min_confidence": 1.5, "days_ahead": 14},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
            "tax": "nan",
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={
            "levels": [
                {"min_amount": 10, "roles": ["accountant"], "step": 0},
            ]
        },
    )
    assert resp.status_code == 422, resp.text
