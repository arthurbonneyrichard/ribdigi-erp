"""GRN rejection_reason OpenAPI honesty (BR-6.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import GrnItemCreate

ROOT = Path(__file__).resolve().parents[2]


def test_grn_reject_reason_ui_wired():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Enter a rejection reason for lines with rejected qty" in page
    assert "Rejected qty requires a reason" in page


def test_grn_item_schema_requires_reason_when_rejected():
    ok = GrnItemCreate.model_validate(
        {
            "po_item_id": "x",
            "received_qty": 10,
            "accepted_qty": 8,
            "rejected_qty": 2,
            "rejection_reason": "Damaged",
        }
    )
    assert ok.rejection_reason == "Damaged"

    # Full accept — reason optional
    GrnItemCreate.model_validate(
        {"po_item_id": "x", "received_qty": 5, "accepted_qty": 5, "rejected_qty": 0}
    )

    with pytest.raises(ValidationError) as explicit:
        GrnItemCreate.model_validate(
            {
                "po_item_id": "x",
                "received_qty": 10,
                "accepted_qty": 8,
                "rejected_qty": 2,
            }
        )
    assert "rejection_reason" in str(explicit.value).lower()

    # Inferred reject when accepted < received and rejected_qty omitted/0
    with pytest.raises(ValidationError) as inferred:
        GrnItemCreate.model_validate(
            {
                "po_item_id": "x",
                "received_qty": 10,
                "accepted_qty": 7,
                "rejected_qty": 0,
            }
        )
    assert "rejection_reason" in str(inferred.value).lower()

    with pytest.raises(ValidationError) as blank:
        GrnItemCreate.model_validate(
            {
                "po_item_id": "x",
                "received_qty": 10,
                "accepted_qty": 8,
                "rejected_qty": 2,
                "rejection_reason": "  ",
            }
        )
    assert "rejection_reason" in str(blank.value).lower()
