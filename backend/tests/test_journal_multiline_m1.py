"""Multi-line manual journal create (BR-10.2) — N≥2 balanced lines."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_multiline_journal_ui_wired():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "manualLines" in accounting
    assert "Add line" in accounting
    assert 'aria-label="Manual journal lines"' in accounting
    assert "Post balanced entry" in accounting
    assert "emptyManualLine" in accounting


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_journal_create_three_lines_balanced(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    # Seed default COA via list (same pattern as unpost suite).
    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    by_code = {a["code"]: a for a in listed.json()["data"]}
    assert "1000" in by_code and "6000" in by_code
    # Prefer a second expense/COGS code when present; else create one.
    second = "5000" if "5000" in by_code else None
    if not second:
        created_acct = await ac.post(
            "/api/v1/accounting/accounts",
            headers=headers,
            json={"code": "6100", "name": "Misc Expense", "account_type": "expense"},
        )
        assert created_acct.status_code == 200, created_acct.text
        second = "6100"

    created = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Multi-line adjusting entry demo",
            "lines": [
                {"account_code": "6000", "debit": 40, "credit": 0},
                {"account_code": second, "debit": 60, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 100},
            ],
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data.get("description") == "Multi-line adjusting entry demo"
    lines = data.get("lines") or []
    assert len(lines) >= 3
    debit = sum(float(l.get("debit") or 0) for l in lines)
    credit = sum(float(l.get("credit") or 0) for l in lines)
    assert abs(debit - credit) <= 0.01
    assert abs(debit - 100) <= 0.01


@pytest.mark.asyncio
async def test_journal_create_unbalanced_rejected(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200
    bad = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Unbalanced",
            "lines": [
                {"account_code": "6000", "debit": 50, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 40},
            ],
        },
    )
    assert bad.status_code == 400, bad.text
