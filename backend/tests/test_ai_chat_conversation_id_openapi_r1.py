"""AiChatBody.conversation_id ∈ UuidIdValue OpenAPI honesty (BR-21.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiChatBody, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_chat_conversation_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = AiChatBody.model_validate({"message": "hello"})
    assert omit.conversation_id is None
    ok = AiChatBody.model_validate(
        {"message": "hello", "conversation_id": f"  {_VALID}  "}
    )
    assert ok.conversation_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "conv_001"):
        with pytest.raises(ValidationError):
            AiChatBody.model_validate({"message": "hello", "conversation_id": bad})


def test_ai_chat_conversation_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI chat conversation_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "conversation_id" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_ai_chat_conversation_id_api_blank_invalid_422(client, seeded):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "conv_001"):
        resp = await ac.post(
            "/api/v1/ai/chat",
            headers=headers,
            json={"message": "hello tip409", "conversation_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    # Valid UUID shape passes schema; service may ignore unknown conversation ids.
    ok_shape = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "hello tip409 missing conv",
            "conversation_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    # AI may be disabled → 503/400; schema must not 422 on valid UUID.
    assert ok_shape.status_code != 422, ok_shape.text
