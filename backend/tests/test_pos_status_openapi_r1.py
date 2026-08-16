"""POS / legacy sale status OpenAPI Literal (BR-8.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PosSaleCreate, TransactionCreate

ROOT = Path(__file__).resolve().parents[2]


def test_pos_sale_status_literal_schema():
    ok = PosSaleCreate.model_validate(
        {
            "total": 1,
            "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
            "status": "completed",
        }
    )
    assert ok.status == "completed"
    defaulted = PosSaleCreate.model_validate(
        {
            "total": 1,
            "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
        }
    )
    assert defaulted.status == "completed"

    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "total": 1,
                "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
                "status": "",
            }
        )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "total": 1,
                "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
                "status": "draft",
            }
        )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "total": 1,
                "items": [{"product_id": "p1", "quantity": 1, "unit_price": 1}],
                "status": "garbage_xyz",
            }
        )

    tx = TransactionCreate.model_validate({})
    assert tx.status == "completed"
    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"status": "pending"})


def test_pos_sale_status_ui_and_docs():
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "status: 'completed'" in pos
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'Literal["completed"]' in api
    assert "422" in api
