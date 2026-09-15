"""JournalLineCreate.account_id ∈ UuidIdValue OpenAPI honesty (BR-10.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import JournalLineCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_journal_line_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = JournalLineCreate.model_validate(
        {"account_code": "6000", "debit": 1, "credit": 0}
    )
    assert omit.account_id is None
    ok = JournalLineCreate.model_validate(
        {"account_id": f"  {_VALID}  ", "debit": 1, "credit": 0}
    )
    assert ok.account_id == _VALID.lower()
    nullish = JournalLineCreate.model_validate(
        {"account_id": None, "account_code": "6000", "debit": 1, "credit": 0}
    )
    assert nullish.account_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "acct_001", "a b"):
        with pytest.raises(ValidationError):
            JournalLineCreate.model_validate({"account_id": bad, "debit": 1, "credit": 0})


def test_journal_line_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Journal line ${idx + 1} account`}' in page
    assert "account_id: l.account_id.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal line account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Journal line N account" in docs
    assert "POST /accounting/journal-entries" in docs


@pytest.mark.asyncio
async def test_journal_line_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:6]

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    by_code = {a["code"]: a for a in listed.json().get("data") or []}
    credit = by_code.get("1000") or next(iter(by_code.values()), None)
    assert credit, listed.json()
    credit_id = credit["id"]
    credit_code = credit["code"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/accounting/journal-entries",
            headers=headers,
            json={
                "description": f"Tip 306 bad {suffix}",
                "lines": [
                    {"account_id": bad, "debit": 12, "credit": 0},
                    {"account_id": credit_id, "debit": 0, "credit": 12},
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": f"Tip 306 missing {suffix}",
            "lines": [
                {"account_id": f"  {str(uuid4()).upper()}  ", "debit": 12, "credit": 0},
                {"account_id": credit_id, "debit": 0, "credit": 12},
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422

    # account_code path still accepted when account_id omitted.
    ok_code = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": f"Tip 306 code OK {suffix}",
            "lines": [
                {"account_code": "6000", "debit": 9, "credit": 0},
                {"account_code": credit_code, "debit": 0, "credit": 9},
            ],
        },
    )
    assert ok_code.status_code == 200, ok_code.text
