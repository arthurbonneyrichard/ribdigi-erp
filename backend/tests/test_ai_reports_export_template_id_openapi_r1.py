"""AiReportsExportBody.template_id ∈ UuidIdValue OpenAPI honesty (BR-21.7)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiReportsExportBody, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_reports_export_template_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = AiReportsExportBody.model_validate({"prompt": "monthly sales"})
    assert omit.template_id is None
    ok = AiReportsExportBody.model_validate({"template_id": f"  {_VALID}  "})
    assert ok.template_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "tmpl_001"):
        with pytest.raises(ValidationError):
            AiReportsExportBody.model_validate({"template_id": bad})


def test_ai_reports_export_template_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI reports export template_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "template_id" in docs
    assert "UuidIdValue" in docs
    assert "/ai/reports/export" in docs


@pytest.mark.asyncio
async def test_ai_reports_export_template_id_api_blank_invalid_422(client, seeded):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "tmpl_001"):
        resp = await ac.post(
            "/api/v1/ai/reports/export",
            headers=headers,
            json={"template_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/ai/reports/export",
        headers=headers,
        json={"template_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
