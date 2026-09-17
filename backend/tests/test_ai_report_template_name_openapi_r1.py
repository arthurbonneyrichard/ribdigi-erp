"""AiReportTemplateCreateBody.name OpenAPI honesty (BR-21.7)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AiReportTemplateCreateBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_report_template_name_schema():
    ok = AiReportTemplateCreateBody.model_validate(
        {"name": "  Monthly Sales  ", "prompt": "monthly sales"}
    )
    assert ok.name == "Monthly Sales"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            AiReportTemplateCreateBody.model_validate(
                {"name": bad, "prompt": "monthly sales"}
            )


def test_ai_report_template_name_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI report template name"' in page
    assert "tmplName.trim()" in page
    assert 'aria-label="Save AI report template"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI report template name OpenAPI" in agents
    assert "AiReportTemplateNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiReportTemplateNameValue" in docs
    assert "AI report template name" in docs


@pytest.mark.asyncio
async def test_ai_report_template_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/ai/reports/templates",
            headers=headers,
            json={"name": bad, "prompt": "monthly sales", "format": "csv"},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={
            "name": f"  Tip142 Template {suffix}  ",
            "prompt": "monthly sales for this month",
            "format": "csv",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip142 Template {suffix}"
