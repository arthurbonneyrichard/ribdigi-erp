"""AI report prompt ∈ AiReportPromptValue OpenAPI (BR-21.7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AiReportPromptValue,
    AiReportsExportBody,
    AiReportsGenerateBody,
    AiReportTemplateCreateBody,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_prompt = TypeAdapter(AiReportPromptValue)


def test_ai_report_prompt_value_schema():
    assert _prompt.validate_python("  monthly sales for this month  ") == (
        "monthly sales for this month"
    )
    with pytest.raises(ValidationError):
        _prompt.validate_python("")
    with pytest.raises(ValidationError):
        _prompt.validate_python("!!!")
    with pytest.raises(ValidationError):
        _prompt.validate_python("http://evil.example/p")
    with pytest.raises(ValidationError):
        _prompt.validate_python("a" * 16001)

    ok_create = AiReportTemplateCreateBody.model_validate(
        {"name": "T", "prompt": "  low stock report  "}
    )
    assert ok_create.prompt == "low stock report"

    with pytest.raises(ValidationError):
        AiReportTemplateCreateBody.model_validate(
            {"name": "T", "prompt": "!!!"}
        )
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate({"prompt": "!!!"})
    with pytest.raises(ValidationError):
        AiReportsGenerateBody.model_validate(
            {"prompt": "", "report_type": "sales_monthly"}
        )
    # omit prompt OK when report_type present
    structured = AiReportsGenerateBody.model_validate(
        {"report_type": "sales_monthly", "format": "csv"}
    )
    assert structured.prompt is None
    with pytest.raises(ValidationError):
        AiReportsExportBody.model_validate({"prompt": "http://x"})


def test_ai_report_prompt_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI chat message"' in page
    assert 'aria-label="Save AI report template"' in page
    assert "AI report prompt is required" in page
    assert "q.trim() || 'monthly sales for this month'" in page  # generate/export fallback
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI report prompt OpenAPI" in agents
    assert "AiReportPromptValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportPromptValue" in docs
    assert "1–16000" in docs


@pytest.mark.asyncio
async def test_ai_report_prompt_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    garbage = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "Tip211 garbage", "prompt": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={"name": "Tip211 url", "prompt": "http://evil.example/p"},
    )
    assert urlish.status_code == 422, urlish.text

    gen_bad = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": "!!!", "format": "csv"},
    )
    assert gen_bad.status_code == 422, gen_bad.text

    hello = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={
            "name": "AiReportPromptValue hello-world",
            "prompt": "monthly sales for this month",
            "format": "csv",
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["name"] == "AiReportPromptValue hello-world"
    assert data["prompt"] == "monthly sales for this month"
    assert data["id"]
