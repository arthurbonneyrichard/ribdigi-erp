"""AiReportsExportBody.period ∈ AiReportPeriodValue OpenAPI (BR-21.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiReportPeriodValue, AiReportsExportBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_period = TypeAdapter(AiReportPeriodValue)


def test_ai_report_export_period_schema():
    assert _period.validate_python("  this_month  ") == "this_month"
    ok = AiReportsExportBody.model_validate(
        {"report_type": "sales_monthly", "period": "  last_month  "}
    )
    assert ok.period == "last_month"
    omit = AiReportsExportBody.model_validate({"prompt": "monthly sales"})
    assert omit.period is None
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 81):
        with pytest.raises(ValidationError):
            AiReportsExportBody.model_validate(
                {"report_type": "sales_monthly", "period": bad}
            )


def test_ai_report_export_period_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI report period"' in page
    assert 'aria-label="Export AI report"' in page
    assert "body: JSON.stringify({ prompt, format: 'csv', period })" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI reports export period OpenAPI" in agents
    assert "AiReportsExportBody.period" in agents
    assert "AiReportPeriodValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportsExportBody" in docs
    assert "AiReportPeriodValue" in docs
    assert '"period"?' in docs or "period" in docs


@pytest.mark.asyncio
async def test_ai_report_export_period_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/ai/reports/export",
            headers=headers,
            json={
                "report_type": "sales_monthly",
                "format": "csv",
                "period": bad,
            },
        )
        assert r.status_code == 422, (bad, r.text)

    omit = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={
            "prompt": "TIP242 omit period monthly sales for this month",
            "format": "csv",
        },
    )
    assert omit.status_code == 200, omit.text
    assert "text/csv" in (omit.headers.get("content-type") or "") or omit.content

    hello = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={
            "report_type": "sales_monthly",
            "format": "csv",
            "period": "  this_month  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.content
