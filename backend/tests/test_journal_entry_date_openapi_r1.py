"""JournalCreate.entry_date OpenAPI honesty (BR-10.2)."""

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


def test_journal_entry_date_schema():
    base = {"description": "adj", "lines": _BASE_LINES}
    omit = JournalCreate.model_validate(base)
    assert omit.entry_date is None
    ok = JournalCreate.model_validate({**base, "entry_date": " 2026-08-01 "})
    assert ok.entry_date == "2026-08-01"
    iso = JournalCreate.model_validate({**base, "entry_date": "2026-08-01T12:00:00"})
    assert iso.entry_date == "2026-08-01T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            JournalCreate.model_validate({**base, "entry_date": bad})


def test_journal_entry_date_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Journal entry date"' in page
    assert "entryDate.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal entry_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Journal entry date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_journal_entry_date_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            "/api/v1/accounting/journal-entries",
            headers=headers,
            json={
                "description": f"Bad date {uuid4().hex[:6]}",
                "entry_date": bad,
                "lines": _BASE_LINES,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": f"Ok date {uuid4().hex[:6]}",
            "entry_date": "2026-08-01",
            "lines": _BASE_LINES,
        },
    )
    assert ok.status_code == 200, ok.text
    assert str(ok.json()["data"]["entry_date"]).startswith("2026-08-01")

    omit = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": f"Omit date {uuid4().hex[:6]}",
            "lines": _BASE_LINES,
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("entry_date")
