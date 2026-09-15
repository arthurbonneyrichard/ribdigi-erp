"""OpenAPI honesty tips #511–#514: FiniteMoneyValue + AiReportFilters."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AiReportFilters,
    AiReportsGenerateBody,
    BankStatementCreateBody,
    FiniteMoneyValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_money = TypeAdapter(FiniteMoneyValue)


def test_finite_money_and_ai_filters_schema():
    assert _money.validate_python(12.5) == 12.5
    assert _money.validate_python(0) == 0.0
    for bad in (float("nan"), float("inf"), float("-inf"), 1e16, -1e16):
        with pytest.raises(ValidationError):
            _money.validate_python(bad)

    body = BankStatementCreateBody.model_validate(
        {"account_id": str(uuid4()), "opening_balance": 10, "closing_balance": 20}
    )
    assert body.opening_balance == 10
    with pytest.raises(ValidationError):
        BankStatementCreateBody.model_validate(
            {"account_id": str(uuid4()), "opening_balance": float("nan")}
        )

    ok = AiReportFilters.model_validate(
        {"warehouse_id": str(uuid4()), "year": 2026, "month": 8, "days": 30}
    )
    assert ok.year == 2026
    for bad in (
        {"evil": True},
        {"warehouse_id": "w1"},
        {"year": 1999},
        {"month": 13},
        {"days": 0},
        {"from_date": "not-a-date"},
    ):
        with pytest.raises(ValidationError):
            AiReportFilters.model_validate(bad)

    gen = AiReportsGenerateBody.model_validate(
        {"report_type": "sales_monthly", "filters": {"month": 8, "year": 2026}}
    )
    assert gen.filters is not None and gen.filters.month == 8


def test_finite_money_ai_filters_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Bank statement money OpenAPI",
        "Bank statement import money Query OpenAPI",
        "AI document expected_amount Form OpenAPI",
        "AI report filters/params OpenAPI",
    ):
        assert title in agents, title
    assert "FiniteMoneyValue" in agents
    assert "AiReportFilters" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "FiniteMoneyValue" in docs
    assert "AiReportFilters" in docs

    acct = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Statement opening balance"' in acct
    assert 'aria-label="Statement closing balance"' in acct
    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI document expected amount"' in ai
    assert "fd.append('expected_amount'" in ai


@pytest.mark.asyncio
async def test_bank_import_money_and_ai_filters_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    account = str(uuid4())
    files = {"file": ("stmt.csv", b"Date,Amount,Description\n2024-01-01,1.00,x\n", "text/csv")}

    for bad in ("nan", "inf", "1e20"):
        resp = await ac.post(
            f"/api/v1/accounting/bank-statements/import?account_id={account}&opening_balance={bad}",
            headers=headers,
            files=files,
        )
        assert resp.status_code == 422, (bad, resp.text)

    # AI filters unknown key / bad uuid
    for body in (
        {"report_type": "sales_monthly", "filters": {"evil": 1}},
        {"report_type": "sales_monthly", "params": {"warehouse_id": "not-a-uuid"}},
        {"report_type": "sales_monthly", "filters": {"year": 1999}},
    ):
        resp = await ac.post("/api/v1/ai/reports/generate", headers=headers, json=body)
        assert resp.status_code == 422, (body, resp.text)

    ok = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": "monthly sales for this month", "format": "csv"},
    )
    assert ok.status_code == 200, ok.text
