"""Expense category soft-deactivate UI + inactive create guard (BR-9.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_category_deactivate_ui_wired():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "setCategoryActive" in expenses
    assert "Deactivate" in expenses
    assert "Activate" in expenses
    assert "[inactive]" in expenses
    assert "is_active" in expenses
    assert "categoryManageFilter" in expenses
    assert 'aria-label="Expense category status filter"' in expenses
    assert "managedCategories" in expenses


@pytest.mark.asyncio
async def test_expense_categories_list_is_active_filter(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    created = await ac.post(
        "/api/v1/expenses/categories",
        headers=admin,
        json={"code": "FLTGL", "name": "Filter Demo Cat", "budget_amount": 0},
    )
    assert created.status_code == 200, created.text
    cat_id = created.json()["data"]["id"]

    await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=admin,
        json={"is_active": False},
    )

    all_rows = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cat_id in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/expenses/categories?is_active=true", headers=admin)
    assert cat_id not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get("/api/v1/expenses/categories?is_active=false", headers=admin)
    assert cat_id in {r["id"] for r in inactive_only.json()["data"]}
    assert all(r["is_active"] is False for r in inactive_only.json()["data"])


@pytest.mark.asyncio
async def test_inactive_category_blocked_on_expense_create(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    created = await ac.post(
        "/api/v1/expenses/categories",
        headers=admin,
        json={"code": "OLDGL", "name": "Obsolete GL Cat", "budget_amount": 0},
    )
    assert created.status_code == 200, created.text
    cat_id = created.json()["data"]["id"]

    deact = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    blocked = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 12,
            "payment_method": "cash",
            "description": "Should fail inactive category",
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.text.lower()

    react = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    ok = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 12,
            "payment_method": "cash",
            "description": "Ok after reactivate",
        },
    )
    assert ok.status_code == 200, ok.text
