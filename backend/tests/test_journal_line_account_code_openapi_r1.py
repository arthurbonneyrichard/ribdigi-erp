"""JournalLineCreate / OpeningBalanceLine.account_code ∈ AccountCodeValue OpenAPI."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import JournalLineCreate, OpeningBalanceLine
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_journal_line_account_code_schema():
    omit = JournalLineCreate.model_validate({"debit": 1, "credit": 0})
    assert omit.account_code is None
    ok = JournalLineCreate.model_validate(
        {"account_code": " 6000 ", "debit": 1, "credit": 0}
    )
    assert ok.account_code == "6000"
    for bad in ("", " ", "!!!", "a b", "http://x", "-100", "_X"):
        with pytest.raises(ValidationError):
            JournalLineCreate.model_validate(
                {"account_code": bad, "debit": 1, "credit": 0}
            )

    open_ok = OpeningBalanceLine.model_validate(
        {"account_code": " 1000 ", "amount": 10}
    )
    assert open_ok.account_code == "1000"
    with pytest.raises(ValidationError):
        OpeningBalanceLine.model_validate({"account_code": "!!!", "amount": 10})


def test_journal_line_account_code_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Journal line ${idx + 1} account code`}' in page
    assert 'aria-label="Opening balance account code"' in page
    assert "account_code: l.account_code.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Journal line account code OpenAPI" in agents
    assert "AccountCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Journal line N account code" in docs
    assert "Opening balance account code" in docs
    assert "lines[].account_code" in docs


@pytest.mark.asyncio
async def test_journal_line_account_code_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:6]

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
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

    for bad in ("!!!", "", "a b", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/accounting/journal-entries",
            headers=headers,
            json={
                "description": f"TIP231 bad {suffix}",
                "lines": [
                    {"account_code": bad, "debit": 15, "credit": 0},
                    {"account_code": credit_code, "debit": 0, "credit": 15},
                ],
            },
        )
        assert r.status_code == 422, (bad, r.text)

        open_r = await ac.post(
            "/api/v1/accounting/opening-balances",
            headers=headers,
            json={"lines": [{"account_code": bad, "amount": 10}]},
        )
        assert open_r.status_code == 422, (bad, open_r.text)

    hello = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": f"TIP231 journal account code OK {suffix}",
            "lines": [
                {"account_code": f"  {debit_code}  ", "debit": 17, "credit": 0},
                {"account_code": credit_code, "debit": 0, "credit": 17},
            ],
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["description"].startswith("TIP231 journal account code OK")
    lines = hello.json()["data"]["lines"]
    assert any(float(ln.get("debit") or 0) == 17 for ln in lines)
