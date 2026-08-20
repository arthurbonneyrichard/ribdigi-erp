"""POST /ai/reports/generate typed AiReportsGenerateBody OpenAPI (BR-21.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiReportsGenerateBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_reports_generate_body_schema_forbid():
    ok = AiReportsGenerateBody.model_validate(
        {"prompt": "  monthly sales for this month  ", "format": "CSV"}
    )
    assert ok.prompt == "monthly sales for this month"
    assert ok.format == "csv"

    structured = AiReportsGenerateBody.model_validate(
        {
            "report_type": "Sales_Monthly",
            "period": "  this_month  ",
            "format": "xlsx",
            "params": {"warehouse_id": "w1"},
        }
    )
    assert structured.report_type == "sales_monthly"
    assert structured.period == "this_month"
    assert structured.params == {"warehouse_id": "w1"}

    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"prompt": ""})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"prompt": "!!!"})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"prompt": "hi", "extra": True})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"prompt": "hi", "format": "docx"})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"report_type": "sales"})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"format": "csv"})


def test_ai_reports_generate_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Generate AI report"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI reports generate body OpenAPI" in agents
    assert "AiReportsGenerateBody" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportsGenerateBody" in docs
    assert "POST /ai/reports/generate" in docs
    assert "extra=forbid" in docs


@pytest.mark.asyncio
async def test_ai_reports_generate_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": "monthly sales", "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    empty = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={},
    )
    assert empty.status_code == 422, empty.text

    bad_fmt = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": "monthly sales", "format": "docx"},
    )
    assert bad_fmt.status_code == 422, bad_fmt.text

    bad_type = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"report_type": "sales", "format": "csv"},
    )
    assert bad_type.status_code == 422, bad_type.text

    hello = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={
            "prompt": "AiReportsGenerateBody hello-world monthly sales for this month",
            "format": "csv",
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["report_type"] == "sales_monthly"
    assert data["format"] == "csv"
    assert "row_count" in data
