"""JournalCreate.reference OpenAPI honesty (BR-10.2)."""

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
    {"account_code": "6000", "debit": 25, "credit": 0},
    {"account_code": "1000", "debit": 0, "credit": 25},
]


def test_journal_reference_schema():
    omit = JournalCreate.model_validate(
        {"description": "Manual adjusting entry", "lines": _BASE_LINES}
    )
    assert omit.reference is None
    ok = JournalCreate.model_validate(
        {
            "description": "Manual adjusting entry",
            "reference": "  FY2026-ADJ-01  ",
            "lines": _BASE_LINES,
        }
    )
    assert ok.reference == "FY2026-ADJ-01"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            JournalCreate.model_validate(
                {
                    "description": "Manual adjusting entry",
                    "reference": bad,
                    "lines": _BASE_LINES,
                }
            )


def test_journal_reference_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Journal reference"' in page
    assert "journalRef.trim() || null" in page
    assert 'aria-label="Post balanced entry"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal reference OpenAPI" in agents
    assert "JournalReferenceValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "JournalReferenceValue" in docs
    assert "Journal reference" in docs


@pytest.mark.asyncio
async def test_journal_reference_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    by_code = {a["code"]: a for a in listed.json().get("data") or []}
    # Prefer expense + cash; fall back to any debit-type + credit-type pair.
    debit_code = "6000" if "6000" in by_code else next(
        (c for c, a in by_code.items() if (a.get("account_type") or "").lower() in {"expense", "asset"}),
        None,
    )
    credit_code = "1000" if "1000" in by_code else next(
        (
            c
            for c, a in by_code.items()
            if c != debit_code
            and (a.get("account_type") or "").lower() in {"asset", "liability", "equity", "income"}
        ),
        None,
    )
    assert debit_code and credit_code, listed.json()
    lines = [
        {"account_code": debit_code, "debit": 25, "credit": 0},
        {"account_code": credit_code, "debit": 0, "credit": 25},
    ]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/journal-entries",
            headers=headers,
            json={
                "description": "Tip164 journal",
                "reference": bad,
                "lines": lines,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={"description": "Tip164 omit reference", "lines": lines},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("reference") in (None, "")

    ok = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Tip164 keep reference",
            "reference": f"  TIP164-{suffix}  ",
            "lines": lines,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("reference") == f"TIP164-{suffix}"
