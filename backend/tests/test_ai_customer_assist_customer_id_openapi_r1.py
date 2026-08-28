"""AiCustomerAssistBody.customer_id ∈ UuidIdValue OpenAPI honesty (BR-21.9)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiCustomerAssistBody, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_customer_assist_customer_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = AiCustomerAssistBody.model_validate({})
    assert omit.customer_id is None
    ok = AiCustomerAssistBody.model_validate({"customer_id": f"  {_VALID}  "})
    assert ok.customer_id == _VALID.lower()
    nullish = AiCustomerAssistBody.model_validate({"customer_id": None})
    assert nullish.customer_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "cust-1", "a b"):
        with pytest.raises(ValidationError):
            AiCustomerAssistBody.model_validate({"customer_id": bad})


def test_ai_customer_assist_customer_id_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI customer assist customer"' in page
    assert "customer_id: assistCustomerId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI customer assist body OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AI customer assist customer" in docs
    assert "POST /ai/customer/assist" in docs


@pytest.mark.asyncio
async def test_ai_customer_assist_customer_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust-1"):
        resp = await ac.post(
            "/api/v1/ai/customer/assist",
            headers=headers,
            json={"customer_id": bad, "query": "best customers"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "best customers tip 317"},
    )
    assert omit.status_code == 200, omit.text

    # Valid UUID shape that is not a tenant customer → not 422 (existence is service).
    missing = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={
            "customer_id": f"  {str(uuid4()).upper()}  ",
            "query": "best customers tip 317 missing",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
