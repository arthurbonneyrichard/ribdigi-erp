"""AiReportsGenerateBody.period ∈ AiReportPeriodValue OpenAPI (BR-21.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiReportPeriodValue, AiReportsGenerateBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_period = TypeAdapter(AiReportPeriodValue)


def test_ai_report_period_value_schema():
    assert _period.validate_python("  this_month  ") == "this_month"
    assert _period.validate_python("Q1 2026") == "Q1 2026"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 81):
        with pytest.raises(ValidationError):
            _period.validate_python(bad)

    ok = AiReportsGenerateBody.model_validate(
        {"report_type": "sales_monthly", "period": "  last_month  "}
    )
    assert ok.period == "last_month"
    omit = AiReportsGenerateBody.model_validate({"prompt": "monthly sales"})
    assert omit.period is None
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate(
            {"report_type": "sales_monthly", "period": ""}
        )
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate(
            {"report_type": "sales_monthly", "period": "!!!"}
        )
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate(
            {"report_type": "sales_monthly", "period": "http://evil"}
        )


def test_ai_report_period_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI report period"' in page
    assert "period: reportPeriod.trim() ? reportPeriod.trim() : null" in page or (
        "const period = reportPeriod.trim() ? reportPeriod.trim() : null;" in page
    )
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI report period OpenAPI" in agents
    assert "AiReportPeriodValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportPeriodValue" in docs
    assert "AI report period" in docs


@pytest.mark.asyncio
async def test_ai_report_period_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/ai/reports/generate",
            headers=headers,
            json={
                "report_type": "sales_monthly",
                "format": "csv",
                "period": bad,
            },
        )
        assert r.status_code == 422, (bad, r.text)

    omit = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={
            "prompt": "TIP237 omit period monthly sales for this month",
            "format": "csv",
        },
    )
    assert omit.status_code == 200, omit.text

    hello = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={
            "report_type": "sales_monthly",
            "format": "csv",
            "period": "  this_month  ",
        },
    )
    assert hello.status_code == 200, hello.text
    label = str(hello.json()["data"].get("period_label") or "")
    assert "month" in label.lower() or label == "this_month"
