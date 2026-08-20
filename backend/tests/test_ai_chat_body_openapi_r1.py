"""POST /ai/chat typed AiChatBody OpenAPI (BR-21.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AiChatBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_chat_body_schema_forbid_and_require_message():
    ok = AiChatBody.model_validate({"message": "  Hello  "})
    assert ok.message == "Hello"
    assert ok.prompt is None

    via_prompt = AiChatBody.model_validate({"prompt": "  Via prompt  "})
    assert via_prompt.prompt == "Via prompt"
    assert via_prompt.message is None

    with_opts = AiChatBody.model_validate(
        {
            "message": "hi",
            "context": "  dashboard  ",
            "conversation_id": "  conv_1  ",
        }
    )
    assert with_opts.context == "dashboard"
    assert with_opts.conversation_id == "conv_1"

    with pytest.raises(ValidationError):
        AiChatBody.model_validate({})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": ""})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "   "})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"prompt": ""})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "!!!"})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "http://evil.example/p"})
    with pytest.raises(ValidationError):
        AiChatBody.model_validate({"message": "hi", "extra": True})


def test_ai_chat_body_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI chat message"' in page
    assert 'aria-label="Ask AI chat"' in page
    assert "AI chat message is required" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI chat body OpenAPI" in agents
    assert "AiChatBody" in agents
    assert "AiChatMessageValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiChatBody" in docs
    assert "extra=forbid" in docs
    assert "POST /ai/chat" in docs


@pytest.mark.asyncio
async def test_ai_chat_api_unknown_blank_422(client, monkeypatch):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "hi", "foo": 1},
    )
    assert unknown.status_code == 422, unknown.text

    blank = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": ""},
    )
    assert blank.status_code == 422, blank.text

    punct = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "!!!"},
    )
    assert punct.status_code == 422, punct.text

    omit = await ac.post("/api/v1/ai/chat", headers=headers, json={})
    assert omit.status_code == 422, omit.text

    # Happy path under mock provider (dev-only).
    monkeypatch.setattr("app.config.settings.AI_ENABLED", True)
    monkeypatch.setattr("app.config.settings.AI_PROVIDER", "mock")
    monkeypatch.setattr("app.ai.settings.AI_ENABLED", True)
    monkeypatch.setattr("app.ai.settings.AI_PROVIDER", "mock")

    ok = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "AiChatBody hello-world"},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data.get("mock") is True
    assert "Mock AI" in (data.get("answer") or "")
