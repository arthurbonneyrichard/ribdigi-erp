"""POST /ai/reports/templates typed AiReportTemplateCreateBody OpenAPI (BR-21.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiReportTemplateCreateBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_report_template_create_body_schema_forbid():
    ok = AiReportTemplateCreateBody.model_validate(
        {
            "name": "  Monthly sales  ",
            "prompt": "  monthly sales for this month  ",
            "format": "CSV",
        }
    )
    assert ok.name == "Monthly sales"
    assert ok.prompt == "monthly sales for this month"
    assert ok.format == "csv"

    omit_fmt = AiReportTemplateCreateBody.model_validate(
        {"name": "Low stock", "prompt": "low stock report"}
    )
    assert omit_fmt.format is None

    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate({})
    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate(
            {"name": "", "prompt": "monthly sales"}
        )
    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate(
            {"name": "x", "prompt": ""}
        )
    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate(
            {"name": "x", "prompt": "!!!"}
        )
    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate(
            {"name": "x", "prompt": "monthly sales", "extra": True}
        )
    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate(
            {"name": "x", "prompt": "monthly sales", "format": "docx"}
        )


def test_ai_report_template_create_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI report template name"' in page
    assert "tmplName.trim()" in page
    assert "AI report prompt is required" in page
    assert 'aria-label="Save AI report template"' in page
    assert "saveReportTemplate" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI report template create body OpenAPI" in agents
    assert "AiReportTemplateCreateBody" in agents
    assert "AiReportPromptValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportTemplateCreateBody" in docs
    assert "POST /ai/reports/templates" in docs
    assert "extra=forbid" in docs


@pytest.mark.asyncio
async def test_ai_report_template_create_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "X", "prompt": "monthly sales", "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    blank_name = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "", "prompt": "monthly sales"},
    )
    assert blank_name.status_code == 422, blank_name.text

    blank_prompt = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "X", "prompt": ""},
    )
    assert blank_prompt.status_code == 422, blank_prompt.text

    punct_prompt = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "X", "prompt": "!!!"},
    )
    assert punct_prompt.status_code == 422, punct_prompt.text

    bad_fmt = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "X", "prompt": "monthly sales", "format": "docx"},
    )
    assert bad_fmt.status_code == 422, bad_fmt.text

    hello = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={
            "name": "AiReportTemplateCreateBody hello-world",
            "prompt": "monthly sales for this month",
            "format": "csv",
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["name"] == "AiReportTemplateCreateBody hello-world"
    assert data["report_type"] == "sales_monthly"
    assert data["format"] == "csv"
    assert data["id"]
