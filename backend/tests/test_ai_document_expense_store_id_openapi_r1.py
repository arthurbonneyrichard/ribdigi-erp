"""AiDocumentExpenseCreate.store_id ∈ UuidIdValue OpenAPI honesty (BR-21.8)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiDocumentExpenseCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_document_expense_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = AiDocumentExpenseCreate.model_validate({"amount": 10})
    assert omit.store_id is None
    ok = AiDocumentExpenseCreate.model_validate(
        {"amount": 10, "store_id": f"  {_VALID}  "}
    )
    assert ok.store_id == _VALID.lower()
    nullish = AiDocumentExpenseCreate.model_validate({"amount": 10, "store_id": None})
    assert nullish.store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "st_001", "a b"):
        with pytest.raises(ValidationError):
            AiDocumentExpenseCreate.model_validate({"amount": 10, "store_id": bad})


def test_ai_document_expense_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI document expense store"' in page
    assert "store_id: draftDocStoreId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI document expense store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AI document expense store" in docs
    assert "POST /ai/documents/create-expense" in docs


@pytest.mark.asyncio
async def test_ai_document_expense_store_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "st_001"):
        resp = await ac.post(
            "/api/v1/ai/documents/create-expense",
            headers=headers,
            json={
                "amount": 12.5,
                "description": f"Tip 308 store {suffix}",
                "store_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={
            "amount": 12.5,
            "description": f"Tip 308 omit store {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={
            "amount": 12.5,
            "description": f"Tip 308 missing store {suffix}",
            "store_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
