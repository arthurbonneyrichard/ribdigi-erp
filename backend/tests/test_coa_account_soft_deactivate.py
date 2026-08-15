"""COA account soft-deactivate (BR-10.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_coa_account_soft_deactivate_ui_wired():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "accountManageFilter" in accounting
    assert 'aria-label="Account status filter"' in accounting
    assert "managedAccounts" in accounting
    assert "setAccountActive" in accounting
    assert "activeAccounts" in accounting
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "a.is_active !== false" in expenses


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_account_list_is_active_filter_and_journal_block(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6999", "name": "Filter Demo Expense", "account_type": "expense"},
    )
    assert created.status_code == 200, created.text
    aid = created.json()["data"]["id"]
    assert created.json()["data"]["is_active"] is True

    deact = await ac.patch(
        f"/api/v1/accounting/accounts/{aid}",
        headers=headers,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    all_rows = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert aid in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/accounting/accounts?is_active=true", headers=headers)
    assert aid not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get(
        "/api/v1/accounting/accounts?is_active=false", headers=headers
    )
    assert aid in {r["id"] for r in inactive_only.json()["data"]}

    blocked = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Should fail inactive account",
            "lines": [
                {"account_code": "6999", "debit": 10, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 10},
            ],
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.json()["detail"].lower()

    react = await ac.patch(
        f"/api/v1/accounting/accounts/{aid}",
        headers=headers,
        json={"is_active": True},
    )
    assert react.status_code == 200, react.text
    assert react.json()["data"]["is_active"] is True

    ok = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "OK after reactivate",
            "lines": [
                {"account_code": "6999", "debit": 10, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 10},
            ],
        },
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_inactive_account_blocked_on_expense_category_gl(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6988", "name": "Inactive GL Target", "account_type": "expense"},
    )
    assert created.status_code == 200, created.text
    aid = created.json()["data"]["id"]
    await ac.patch(
        f"/api/v1/accounting/accounts/{aid}",
        headers=headers,
        json={"is_active": False},
    )

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    blocked = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=headers,
        json={"account_id": aid},
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.json()["detail"].lower()
