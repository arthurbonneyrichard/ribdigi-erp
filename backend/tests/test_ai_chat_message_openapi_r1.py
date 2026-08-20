"""AI chat message ∈ AiChatMessageValue OpenAPI (BR-21.1 / BR-21.9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiChatBody, AiChatMessageValue, AiCustomerAssistBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_msg = TypeAdapter(AiChatMessageValue)


def test_ai_chat_message_value_schema():
    assert _msg.validate_python("  Hello world  ") == "Hello world"
    with pytest.raises(ValidationError):
        _msg.validate_python("")
    with pytest.raises(ValidationError):
        _msg.validate_python("!!!")
    with pytest.raises(ValidationError):
        _msg.validate_python("http://evil.example/p")
    with pytest.raises(ValidationError):
        _msg.validate_python("a" * 16001)

    ok = AiChatBody.model_validate({"message": "  Ask sales  "})
    assert ok.message == "Ask sales"
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "!!!"})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "hi", "context": "!!!"})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "hi", "context": ""})

    overview = AiCustomerAssistBody.model_validate({})
    assert overview.query is None
    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"query": "!!!"})
    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"query": ""})
    with pytest.raises(ValidationError):
        AiCustomerAssistBody.model_validate({"message": "http://x"})
    # blank customer_id still omits
    blank_id = AiCustomerAssistBody.model_validate({"customer_id": "   "})
    assert blank_id.customer_id is None


def test_ai_chat_message_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI chat message"' in page
    assert 'aria-label="Ask AI chat"' in page
    assert "AI chat message is required" in page
    assert 'aria-label="Customer assist"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI chat message OpenAPI" in agents
    assert "AiChatMessageValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiChatMessageValue" in docs
    assert "1–16000" in docs


@pytest.mark.asyncio
async def test_ai_chat_message_api_blank_invalid_422(client, monkeypatch):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    chat_garbage = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "!!!"},
    )
    assert chat_garbage.status_code == 422, chat_garbage.text

    chat_url = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "http://evil.example/p"},
    )
    assert chat_url.status_code == 422, chat_url.text

    assist_garbage = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "!!!"},
    )
    assert assist_garbage.status_code == 422, assist_garbage.text

    assist_blank = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": ""},
    )
    assert assist_blank.status_code == 422, assist_blank.text

    overview = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={},
    )
    assert overview.status_code == 200, overview.text

    hello = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "AiChatMessageValue hello-world best customers"},
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["query"] == "AiChatMessageValue hello-world best customers"
    assert data["method"] == "rule_based_rfm"

    monkeypatch.setattr("app.config.settings.AI_ENABLED", True)
    monkeypatch.setattr("app.config.settings.AI_PROVIDER", "mock")
    monkeypatch.setattr("app.ai.settings.AI_ENABLED", True)
    monkeypatch.setattr("app.ai.settings.AI_PROVIDER", "mock")

    chat_ok = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "AiChatMessageValue hello-world"},
    )
    assert chat_ok.status_code == 200, chat_ok.text
    assert chat_ok.json()["data"].get("mock") is True
