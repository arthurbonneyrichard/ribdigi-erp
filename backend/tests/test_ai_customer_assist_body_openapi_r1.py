"""POST /ai/customer/assist typed AiCustomerAssistBody OpenAPI (BR-21.9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiCustomerAssistBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_customer_assist_body_schema_forbid():
    empty = AiCustomerAssistBody.model_validate({})
    assert empty.customer_id is None
    assert empty.query is None
    assert empty.message is None

    ok = AiCustomerAssistBody.model_validate(
        {
            "customer_id": "  cust-1  ",
            "query": "  best customers  ",
        }
    )
    assert ok.customer_id == "cust-1"
    assert ok.query == "best customers"

    via_message = AiCustomerAssistBody.model_validate({"message": "  churn  "})
    assert via_message.message == "churn"

    blank_id = AiCustomerAssistBody.model_validate({"customer_id": "   "})
    assert blank_id.customer_id is None

    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"query": ""})
    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"query": "!!!"})
    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"message": "http://evil.example/p"})
    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"query": "hi", "extra": True})


def test_ai_customer_assist_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer assist"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI customer assist body OpenAPI" in agents
    assert "AiCustomerAssistBody" in agents
    assert "AiChatMessageValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiCustomerAssistBody" in docs
    assert "POST /ai/customer/assist" in docs
    assert "extra=forbid" in docs


@pytest.mark.asyncio
async def test_ai_customer_assist_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "best customers", "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    garbage = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    overview = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={},
    )
    assert overview.status_code == 200, overview.text
    assert overview.json()["data"]["method"] == "rule_based_rfm"

    hello = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "AiCustomerAssistBody hello-world best customers"},
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["method"] == "rule_based_rfm"
    assert data["intent"] == "best"
    assert "answer" in data
