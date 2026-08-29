"""OpenAPI honesty tips #515–#520: PositiveMoneyValue / NonNegativeMoneyValue / FiniteMoney line."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    BankStatementLineCreate,
    CashTransferCreate,
    CustomerPaymentCreate,
    ExpenseCreate,
    FiniteMoneyValue,
    JournalLineCreate,
    NonNegativeMoneyValue,
    OpeningBalanceLine,
    PosSessionClose,
    PosSessionOpen,
    PositiveMoneyValue,
    TaxCalculateRequest,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_pos = TypeAdapter(PositiveMoneyValue)
_nn = TypeAdapter(NonNegativeMoneyValue)
_fin = TypeAdapter(FiniteMoneyValue)


def test_money_value_adapters_and_models():
    assert _pos.validate_python(1.5) == 1.5
    assert _nn.validate_python(0) == 0.0
    assert _fin.validate_python(-12.5) == -12.5

    for bad in (float("nan"), float("inf"), float("-inf"), 0, -1, 1e16):
        with pytest.raises(ValidationError):
            _pos.validate_python(bad)
    for bad in (float("nan"), float("inf"), float("-inf"), -0.01, 1e16):
        with pytest.raises(ValidationError):
            _nn.validate_python(bad)
    for bad in (float("nan"), float("inf"), float("-inf"), 1e16, -1e16):
        with pytest.raises(ValidationError):
            _fin.validate_python(bad)

    ExpenseCreate.model_validate({"amount": 10, "category": "misc"})
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate({"amount": float("inf"), "category": "misc"})

    OpeningBalanceLine.model_validate(
        {"account_id": str(uuid4()), "amount": 100}
    )
    with pytest.raises(ValidationError):
        OpeningBalanceLine.model_validate(
            {"account_id": str(uuid4()), "amount": float("inf")}
        )

    CashTransferCreate.model_validate({"amount": 5})
    with pytest.raises(ValidationError):
        CashTransferCreate.model_validate({"amount": 0})

    CustomerPaymentCreate.model_validate(
        {"customer_id": str(uuid4()), "amount": 9.99}
    )
    with pytest.raises(ValidationError):
        CustomerPaymentCreate.model_validate(
            {"customer_id": str(uuid4()), "amount": float("nan")}
        )

    TaxCalculateRequest.model_validate({"amount": 50})
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate({"amount": -1})

    JournalLineCreate.model_validate(
        {"account_id": str(uuid4()), "debit": 10, "credit": 0}
    )
    with pytest.raises(ValidationError):
        JournalLineCreate.model_validate(
            {"account_id": str(uuid4()), "debit": float("inf"), "credit": 0}
        )

    PosSessionOpen.model_validate({"opening_cash": 0})
    with pytest.raises(ValidationError):
        PosSessionOpen.model_validate({"opening_cash": float("inf")})

    PosSessionClose.model_validate({"actual_cash": 10})
    with pytest.raises(ValidationError):
        PosSessionClose.model_validate({"actual_cash": -1})

    BankStatementLineCreate.model_validate({"amount": -25.5})
    with pytest.raises(ValidationError):
        BankStatementLineCreate.model_validate({"amount": float("nan")})
    with pytest.raises(ValidationError):
        BankStatementLineCreate.model_validate({"amount": 0})


def test_money_value_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Positive / non-negative money OpenAPI",
        "Expense / recurring / AI draft amount OpenAPI",
        "Payment / cash transfer / POS tender amount OpenAPI",
        "Opening balance / tax / approval threshold money OpenAPI",
        "Journal debit/credit + POS session cash OpenAPI",
        "Bank statement line amount OpenAPI",
    ):
        assert title in agents, title
    assert "PositiveMoneyValue" in agents
    assert "NonNegativeMoneyValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PositiveMoneyValue" in docs
    assert "NonNegativeMoneyValue" in docs

    exp = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense amount"' in exp
    assert 'aria-label="OCR expense amount"' in exp
    assert 'aria-label="Recurring amount"' in exp

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Payment amount"' in credit

    acct = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening balance amount"' in acct
    assert 'aria-label="Cash transfer amount"' in acct
    assert 'aria-label="Statement line amount"' in acct

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening cash"' in pos
    assert 'aria-label="Counted cash"' in pos


@pytest.mark.asyncio
async def test_money_value_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for body in (
        {"amount": "inf", "category": "misc"},
        {"amount": "nan", "category": "misc"},
        {"amount": 0, "category": "misc"},
        {"amount": -5, "category": "misc"},
    ):
        resp = await ac.post("/api/v1/expenses", headers=headers, json=body)
        assert resp.status_code == 422, (body, resp.text)

    resp = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": "inf"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": "inf"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={"amount": "nan", "kind": "deposit"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": str(uuid4()),
            "lines": [{"amount": "inf"}],
        },
    )
    assert resp.status_code == 422, resp.text
