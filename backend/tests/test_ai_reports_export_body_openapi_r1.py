"""POST /ai/reports/export typed AiReportsExportBody OpenAPI (BR-21.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiReportsExportBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_reports_export_body_schema_forbid():
    ok = AiReportsExportBody.model_validate(
        {"prompt": "  monthly sales for this month  "}
    )
    assert ok.prompt == "monthly sales for this month"
    assert ok.format == "csv"

    xlsx = AiReportsExportBody.model_validate(
        {"report_type": "Sales_Monthly", "format": "XLSX"}
    )
    assert xlsx.report_type == "sales_monthly"
    assert xlsx.format == "xlsx"

    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({})
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"prompt": ""})
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"prompt": "!!!"})
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"prompt": "hi", "extra": True})
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"prompt": "hi", "format": "docx"})
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"report_type": "sales"})
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"format": ""})


def test_ai_reports_export_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export AI report"' in page
    assert "exportReport" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI reports export body OpenAPI" in agents
    assert "AiReportsExportBody" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportsExportBody" in docs
    assert "POST /ai/reports/export" in docs
    assert "extra=forbid" in docs


@pytest.mark.asyncio
async def test_ai_reports_export_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={"prompt": "monthly sales", "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    empty = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={},
    )
    assert empty.status_code == 422, empty.text

    bad_fmt = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={"prompt": "monthly sales", "format": "docx"},
    )
    assert bad_fmt.status_code == 422, bad_fmt.text

    hello = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={
            "prompt": "AiReportsExportBody hello-world monthly sales for this month",
            "format": "csv",
        },
    )
    assert hello.status_code == 200, hello.text
    assert "text/csv" in hello.headers.get("content-type", "")
    assert "Content-Disposition" in hello.headers
    assert hello.text  # non-empty csv body
