"""AiDocumentExpenseCreate.description OpenAPI honesty (BR-21.8 / BR-9.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AiDocumentExpenseCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_document_expense_description_schema():
    omit = AiDocumentExpenseCreate.model_validate({"amount": 10})
    assert omit.description is None
    ok = AiDocumentExpenseCreate.model_validate(
        {"amount": 10, "description": "  OCR office supplies  "}
    )
    assert ok.description == "OCR office supplies"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            AiDocumentExpenseCreate.model_validate({"amount": 10, "description": bad})


def test_ai_document_expense_description_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI document expense description"' in page
    assert "draftDocDescription.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ExpenseDescriptionValue" in agents
    assert "AiDocumentExpenseCreate.description" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ExpenseDescriptionValue" in docs
    assert "AI document expense description" in docs


@pytest.mark.asyncio
async def test_ai_document_expense_description_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    bad = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=admin,
        json={"amount": 12.5, "description": "!!!!"},
    )
    assert bad.status_code == 422, bad.text

    blank = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=admin,
        json={"amount": 12.5, "description": "   "},
    )
    assert blank.status_code == 422, blank.text

    ok = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=admin,
        json={
            "amount": 12.5,
            "description": f"TIP181 AI desc {suffix}",
            "payee": f"Vendor {suffix}",
        },
    )
    assert ok.status_code == 200, ok.text
    exp = (ok.json().get("data") or {}).get("expense") or ok.json().get("data") or {}
    assert exp.get("description") == f"TIP181 AI desc {suffix}"
