"""OpeningBalanceCreate.notes OpenAPI honesty (BR-10.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import OpeningBalanceCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_opening_balance_notes_schema():
    omit = OpeningBalanceCreate.model_validate(
        {"lines": [{"account_code": "1000", "amount": 1}]}
    )
    assert omit.notes is None
    nullish = OpeningBalanceCreate.model_validate(
        {"lines": [{"account_code": "1000", "amount": 1}], "notes": None}
    )
    assert nullish.notes is None
    ok = OpeningBalanceCreate.model_validate(
        {
            "lines": [{"account_code": "1000", "amount": 1}],
            "notes": "  FY2026 go-live openings  ",
        }
    )
    assert ok.notes == "FY2026 go-live openings"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            OpeningBalanceCreate.model_validate(
                {
                    "lines": [{"account_code": "1000", "amount": 1}],
                    "notes": bad,
                }
            )


def test_opening_balance_notes_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening balance notes"' in page
    assert "coaOpenNotes.trim() || null" in page
    assert 'aria-label="Post opening balances"' in page
    assert "notes: 'COA opening balances'" not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening balance notes OpenAPI" in agents
    assert "OpeningBalanceNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "OpeningBalanceNotesValue" in docs
    assert "Opening balance notes" in docs


@pytest.mark.asyncio
async def test_opening_balance_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    line = {"account_code": "1000", "amount": 12}

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/opening-balances",
            headers=admin,
            json={"lines": [line], "notes": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    status = await ac.get("/api/v1/accounting/opening-balances", headers=admin)
    assert status.status_code == 200, status.text
    already = bool((status.json().get("data") or {}).get("posted"))
    if already:
        return

    ok = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=admin,
        json={
            "lines": [line],
            "reference": f"TIP162-{suffix}",
            "notes": f"  Tip162 notes {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    journal_id = ok.json()["data"]["journal_id"]

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=admin)
    assert journals.status_code == 200, journals.text
    rows = journals.json().get("data") or []
    hit = next((j for j in rows if j.get("id") == journal_id), None)
    assert hit, journals.json()
    assert hit.get("description") == f"Tip162 notes {suffix}", hit
