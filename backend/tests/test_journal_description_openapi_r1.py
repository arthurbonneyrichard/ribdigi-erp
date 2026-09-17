"""JournalCreate.description OpenAPI honesty (BR-10.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import JournalCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE_LINES = [
    {"account_code": "6000", "debit": 50, "credit": 0},
    {"account_code": "1000", "debit": 0, "credit": 50},
]


def test_journal_description_schema():
    ok = JournalCreate.model_validate(
        {"description": "  Manual adjusting entry  ", "lines": _BASE_LINES}
    )
    assert ok.description == "Manual adjusting entry"
    for bad in ("", " ", "!", "!!", "!!!", "http://evil", "@@", "X"):
        with pytest.raises(ValidationError):
            JournalCreate.model_validate({"description": bad, "lines": _BASE_LINES})
    with pytest.raises(ValidationError):
        JournalCreate.model_validate({"lines": _BASE_LINES})


def test_journal_description_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Journal description"' in page
    assert "description.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal description OpenAPI" in agents
    assert "JournalDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Journal description" in docs
    assert "JournalDescriptionValue" in docs


@pytest.mark.asyncio
async def test_journal_description_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/journal-entries",
            headers=headers,
            json={"description": bad, "lines": _BASE_LINES},
        )
        assert resp.status_code == 422, (bad, resp.text)

    label = f"Tip121 description {uuid4().hex[:6]}"
    ok = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={"description": f"  {label}  ", "lines": _BASE_LINES},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["description"] == label
