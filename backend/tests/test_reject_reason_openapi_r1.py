"""OpenAPI hygiene: reject/suspend bodies require reason (Field min_length=1).

Runtime already enforced reasons; empty body previously bypassed schema via
optional payload / Optional reason and returned service 400. Align with PREQ /
Skip-next style so omit/empty → 422 and whitespace → 400.
"""

from __future__ import annotations

from pathlib import Path

from app.schemas import (
    ExpenseReject,
    SalesQuotationReject,
    StockTransferReject,
    TenantSuspendRequest,
)

ROOT = Path(__file__).resolve().parents[2]


def test_reject_suspend_reason_schemas_required():
    for cls in (
        TenantSuspendRequest,
        SalesQuotationReject,
        StockTransferReject,
        ExpenseReject,
    ):
        field = cls.model_fields["reason"]
        assert field.is_required()
        assert field.annotation is str


def test_expense_reject_schema_separate_from_approve_decision():
    schemas = (ROOT / "backend/app/schemas.py").read_text(encoding="utf-8")
    assert "class ExpenseReject(BaseModel):" in schemas
    assert "class ExpenseDecision(BaseModel):" in schemas
    # Approve decision must not carry a silent optional reject reason.
    decision_block = schemas.split("class ExpenseDecision(BaseModel):")[1].split("class ")[0]
    assert "reason" not in decision_block
    assert "comment" in decision_block


def test_api_reject_suspend_payloads_not_optional():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "payload: TenantSuspendRequest | None = None" not in api
    assert "payload: SalesQuotationReject | None = None" not in api
    assert "payload: StockTransferReject | None = None" not in api
    assert "payload: ExpenseReject" in api
    assert "reason=payload.reason or payload.comment" not in api
