"""JournalLineCreate.description OpenAPI honesty (BR-10.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import JournalCreate, JournalLineCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_journal_line_description_schema():
    omit = JournalLineCreate.model_validate(
        {"account_code": "6000", "debit": 1, "credit": 0}
    )
    assert omit.description is None
    nullish = JournalLineCreate.model_validate(
        {"account_code": "6000", "debit": 1, "credit": 0, "description": None}
    )
    assert nullish.description is None
    ok = JournalLineCreate.model_validate(
        {"account_code": "6000", "debit": 1, "credit": 0, "description": "  Office supplies  "}
    )
    assert ok.description == "Office supplies"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            JournalLineCreate.model_validate(
                {"account_code": "6000", "debit": 1, "credit": 0, "description": bad}
            )


def test_journal_line_description_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "l.description.trim() || null" in page
    assert "Journal line ${idx + 1} description" in page or 'Journal line ${idx + 1} description' in page
    assert 'aria-label={`Journal line ${idx + 1} description`}' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal line description OpenAPI" in agents
    assert "JournalLineDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "JournalLineDescriptionValue" in docs
    assert "Journal line N description" in docs


@pytest.mark.asyncio
async def test_journal_line_description_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    tag = f"Tip170 line {suffix}"

    listed = await ac.get("/api/v1/accounting/accounts", headers=admin)
    assert listed.status_code == 200, listed.text
    by_code = {a["code"]: a for a in listed.json().get("data") or []}
    debit_code = "6000" if "6000" in by_code else next(
        (
            c
            for c, a in by_code.items()
            if (a.get("account_type") or "").lower() in {"expense", "asset"}
        ),
        None,
    )
    credit_code = "1000" if "1000" in by_code else next(
        (
            c
            for c, a in by_code.items()
            if c != debit_code
            and (a.get("account_type") or "").lower()
            in {"asset", "liability", "equity", "income"}
        ),
        None,
    )
    assert debit_code and credit_code, listed.json()

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/journal-entries",
            headers=admin,
            json={
                "description": f"Tip170 header {suffix}",
                "lines": [
                    {
                        "account_code": debit_code,
                        "debit": 12,
                        "credit": 0,
                        "description": bad,
                    },
                    {"account_code": credit_code, "debit": 0, "credit": 12},
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=admin,
        json={
            "description": f"Tip170 omit {suffix}",
            "lines": [
                {"account_code": debit_code, "debit": 13, "credit": 0},
                {"account_code": credit_code, "debit": 0, "credit": 13},
            ],
        },
    )
    assert omit.status_code == 200, omit.text
    omit_lines = omit.json()["data"].get("lines") or []
    assert omit_lines and omit_lines[0].get("description") in (None, "")

    ok = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=admin,
        json={
            "description": f"Tip170 keep {suffix}",
            "lines": [
                {
                    "account_code": debit_code,
                    "debit": 14,
                    "credit": 0,
                    "description": f"  {tag}  ",
                },
                {"account_code": credit_code, "debit": 0, "credit": 14},
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    keep_lines = ok.json()["data"].get("lines") or []
    assert keep_lines and keep_lines[0].get("description") == tag, ok.json()

    # Nested schema still rejects when wrapped in JournalCreate
    with pytest.raises(ValidationError):
        JournalCreate.model_validate(
            {
                "description": "ok header",
                "lines": [
                    {
                        "account_code": debit_code,
                        "debit": 1,
                        "credit": 0,
                        "description": "!!!",
                    },
                    {"account_code": credit_code, "debit": 0, "credit": 1},
                ],
            }
        )
