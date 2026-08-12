"""Stage 123 F1 — inactive tax rates / COA / expense categories honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tax_rates_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": "Stage123 Inactive VAT", "rate": 7.5, "tax_type": "vat"},
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/tax/rates/{rid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/tax/rates?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == rid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/tax/rates?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == rid for r in active.json()["data"])


@pytest.mark.asyncio
async def test_accounts_and_expense_categories_is_active(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6999", "name": "Stage123 Temp Expense", "account_type": "expense"},
    )
    assert created.status_code == 200, created.text
    aid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/accounting/accounts/{aid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get(
        "/api/v1/accounting/accounts?is_active=false&active_only=false", headers=headers
    )
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == aid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/accounting/accounts?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == aid for r in active.json()["data"])

    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "INA123", "name": "Soon Inactive Exp Cat", "budget_amount": 100},
    )
    assert cat.status_code == 200, cat.text
    cid = cat.json()["data"]["id"]
    await ac.patch(
        f"/api/v1/expenses/categories/{cid}",
        headers=headers,
        json={"is_active": False},
    )
    cats_inactive = await ac.get("/api/v1/expenses/categories?is_active=false", headers=headers)
    assert cats_inactive.status_code == 200, cats_inactive.text
    assert any(r["id"] == cid for r in cats_inactive.json()["data"])
    assert all(r.get("is_active") is False for r in cats_inactive.json()["data"])


def test_shell_and_ui_inactive_finance_masters_f1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "tax_active=false" in shell
    assert "Inactive Tax Rates" in shell
    assert "account_active=false" in shell
    assert "Inactive Accounts" in shell
    assert "expense_category_active=false" in shell
    assert "Inactive Expense Categories" in shell
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "Stage 123" in tax
    assert "taxActiveFilter" in tax
    acc = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 123" in acc
    assert "accountActiveFilter" in acc
    exp = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Stage 123" in exp
    assert "expenseCategoryActiveFilter" in exp
