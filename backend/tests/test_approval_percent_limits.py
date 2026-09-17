"""Percentage approval limits on expense/PR matrices (RBAC §14).

Extends existing ``min_amount`` matrix with optional ``min_percent``. Expense
create uses category budget as percent basis (amount ÷ budget × 100). Does not
claim overall RBAC Complete or store-scoped RBAC Complete.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.expenses import (
    category_budget_percent_basis,
    normalize_approval_matrix,
    steps_required_from_matrix,
)
from app import models as m
from tests.conftest import auth_headers


def test_normalize_accepts_optional_min_percent():
    levels = normalize_approval_matrix(
        {
            "levels": [
                {
                    "min_amount": 100,
                    "min_percent": 10,
                    "roles": ["store_manager"],
                    "label": "L1",
                },
                {
                    "min_amount": 1000,
                    "min_percent": 50,
                    "roles": ["company_admin"],
                    "label": "L2",
                },
            ]
        }
    )
    assert levels[0]["min_percent"] == pytest.approx(10)
    assert levels[1]["min_percent"] == pytest.approx(50)


def test_normalize_rejects_non_increasing_min_percent():
    with pytest.raises(HTTPException) as ei:
        normalize_approval_matrix(
            {
                "levels": [
                    {
                        "min_amount": 100,
                        "min_percent": 40,
                        "roles": ["store_manager"],
                        "label": "L1",
                    },
                    {
                        "min_amount": 1000,
                        "min_percent": 20,
                        "roles": ["company_admin"],
                        "label": "L2",
                    },
                ]
            }
        )
    assert ei.value.status_code == 400
    assert "min_percent" in str(ei.value.detail)


def test_normalize_rejects_min_percent_out_of_range():
    with pytest.raises(HTTPException) as ei:
        normalize_approval_matrix(
            {
                "levels": [
                    {
                        "min_amount": 100,
                        "min_percent": 150,
                        "roles": ["store_manager"],
                        "label": "L1",
                    }
                ]
            }
        )
    assert ei.value.status_code == 400


def test_steps_required_or_logic_amount_or_percent():
    levels = normalize_approval_matrix(
        {
            "levels": [
                {
                    "min_amount": 500,
                    "min_percent": 10,
                    "roles": ["store_manager"],
                    "label": "L1",
                },
                {
                    "min_amount": 5000,
                    "min_percent": 40,
                    "roles": ["company_admin"],
                    "label": "L2",
                },
            ]
        }
    )
    # Small amount, no percent → auto
    assert steps_required_from_matrix(50, levels) == 0
    # Small amount, percent hits L1 only
    assert steps_required_from_matrix(50, levels, percent=15) == 1
    # Small amount, percent hits L1+L2
    assert steps_required_from_matrix(50, levels, percent=45) == 2
    # Large amount hits L1 via amount even if percent None
    assert steps_required_from_matrix(600, levels) == 1
    # Amount hits L1; percent hits L2 → 2 steps
    assert steps_required_from_matrix(600, levels, percent=45) == 2


def test_backward_compat_levels_without_min_percent():
    levels = normalize_approval_matrix(
        {
            "levels": [
                {"min_amount": 100, "roles": ["store_manager"], "label": "L1"},
                {"min_amount": 1000, "roles": ["company_admin"], "label": "L2"},
            ]
        }
    )
    assert levels[0]["min_percent"] is None
    assert steps_required_from_matrix(150, levels) == 1
    assert steps_required_from_matrix(150, levels, percent=99) == 1  # no pct thresholds


@pytest.mark.asyncio
async def test_expense_settings_persist_min_percent(client):
    ac, seed = client
    import pyotp

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    res = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={
            "levels": [
                {
                    "min_amount": 100,
                    "min_percent": 12.5,
                    "roles": ["store_manager"],
                    "label": "L1",
                },
                {
                    "min_amount": 1000,
                    "min_percent": 40,
                    "roles": ["super_admin"],
                    "label": "L2",
                },
            ]
        },
    )
    assert res.status_code == 200, res.text
    levels = res.json()["data"]["levels"]
    assert float(levels[0]["min_percent"]) == pytest.approx(12.5)
    assert float(levels[1]["min_percent"]) == pytest.approx(40)

    got = await ac.get("/api/v1/expenses/settings", headers=headers)
    assert got.status_code == 200
    again = got.json()["data"]["levels"]
    assert float(again[0]["min_percent"]) == pytest.approx(12.5)


@pytest.mark.asyncio
async def test_expense_create_triggers_on_budget_percent(client, db_session):
    """Amount under monetary L1 but over budget % still requires approval."""
    ac, seed = client
    import pyotp

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    mgr_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    store = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="Pct Limit Store",
        code="PCT-LIM",
        manager_id=seed["mgr1"].id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store.id,
        name="Pct WH",
        code="WH-PCT",
        warehouse_type="retail",
        is_active=True,
    )
    db_session.add(wh)

    # High monetary thresholds; low percent threshold
    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={
            "levels": [
                {
                    "min_amount": 10_000,
                    "min_percent": 20,
                    "roles": ["store_manager"],
                    "label": "L1",
                },
                {
                    "min_amount": 50_000,
                    "min_percent": 60,
                    "roles": ["super_admin"],
                    "label": "L2",
                },
            ]
        },
    )
    assert settings.status_code == 200, settings.text

    # Category budget 1000 → 250 is 25% (>20%) but << 10000 amount threshold
    cat = m.ExpenseCategory(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        code="PCTBUD",
        name="Pct Budget Cat",
        budget_amount=1000,
        is_active=True,
    )
    db_session.add(cat)
    await db_session.commit()

    basis = await category_budget_percent_basis(
        db_session,
        tenant_id=seed["t1"].id,
        category_id=cat.id,
        amount=250,
        company_id=seed["c1"].id,
    )
    assert basis == pytest.approx(25.0)

    created = await ac.post(
        "/api/v1/expenses",
        headers=mgr_h,
        json={
            "amount": 250,
            "description": "pct-limit trigger",
            "category_id": cat.id,
            "payment_method": "cash",
            "store_id": store.id,
        },
    )
    assert created.status_code in (200, 201), created.text
    body = created.json()["data"]
    assert body["status"] == "pending"
    assert int(body["approval_steps_required"]) >= 1
