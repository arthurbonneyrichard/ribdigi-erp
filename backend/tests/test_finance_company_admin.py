"""Focused company-admin finance checks: expenses, ledger, credit, tax, isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import accounting as accounting_svc
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_expense_journal_posted_once(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Supplies",
            "amount": 40,
            "description": "Stationery pack",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    expense_id = created.json()["data"]["id"]
    status = created.json()["data"]["status"]
    if status != "approved":
        pytest.skip("expense required approval; journal posts on approve")

    first = (
        await db_session.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == expense_id,
                m.JournalEntry.status == "posted",
            )
        )
    ).scalar_one()
    assert first == 1

    row = await db_session.get(m.Expense, expense_id)
    again = await accounting_svc.post_expense_journal(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["mgr1"].id,
        expense=row,
    )
    await db_session.commit()
    second = (
        await db_session.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == expense_id,
                m.JournalEntry.status == "posted",
            )
        )
    ).scalar_one()
    assert second == 1
    assert again.id is not None


@pytest.mark.asyncio
async def test_expenses_isolated_from_other_company(client):
    ac, seed = client
    alpha = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    created = await ac.post(
        "/api/v1/expenses",
        headers=alpha,
        json={
            "category": "Utilities",
            "amount": 12,
            "description": "Alpha only",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    expense_id = created.json()["data"]["id"]
    listed = await ac.get("/api/v1/expenses", headers=beta)
    assert listed.status_code in {200, 403}
    if listed.status_code == 200:
        ids = {row["id"] for row in listed.json()["data"]}
        assert expense_id not in ids
    missing = await ac.get(f"/api/v1/expenses/{expense_id}", headers=beta)
    assert missing.status_code in {403, 404}


@pytest.mark.asyncio
async def test_credit_limit_requires_approve_not_sales_write(client, db_session):
    ac, seed = client
    officer = m.User(
        tenant_id=seed["t1"].id,
        email="sales@alpha.example.com",
        full_name="Sales Officer",
        password_hash=hash_password("SecurePass123!"),
        role="sales_officer",
        email_verified=True,
        permissions=permissions_for_role("sales_officer"),
        totp_enabled=False,
    )
    db_session.add(officer)
    await db_session.commit()

    headers = await auth_headers(ac, email="sales@alpha.example.com", tenant_slug="alpha")
    r = await ac.patch(
        f"/api/v1/customers/{seed['party1'].id}/credit-limit",
        headers=headers,
        json={"credit_limit": 500, "payment_terms_days": 14},
    )
    assert r.status_code == 403

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    ok = await ac.patch(
        f"/api/v1/customers/{seed['party1'].id}/credit-limit",
        headers=mgr,
        json={"credit_limit": 500, "payment_terms_days": 14},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["credit_limit"] == 500


@pytest.mark.asyncio
async def test_credit_aging_isolated(client):
    ac, seed = client
    alpha = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/credit/aging?kind=receivable", headers=alpha)
    assert r.status_code == 200, r.text
    names = {p["name"] for p in r.json()["data"].get("parties") or []}
    assert "Beta Customer" not in names


@pytest.mark.asyncio
async def test_tax_rates_isolated_and_calculate_uses_server(client, db_session):
    ac, seed = client
    beta_admin = m.User(
        tenant_id=seed["t2"].id,
        email="admin@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    db_session.add(beta_admin)
    await db_session.commit()
    alpha = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/tax/rates",
        headers=alpha,
        json={
            "name": "Alpha VAT",
            "rate": 15,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": True,
            "is_active": True,
        },
    )
    assert created.status_code == 200, created.text
    rate_id = created.json()["data"]["id"]

    preview = await ac.post(
        "/api/v1/tax/calculate",
        headers=alpha,
        json={"amount": 100},
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["net"] == 100
    assert data["tax"] == 15
    assert data["gross"] == 115

    beta = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    listed = await ac.get("/api/v1/tax/rates", headers=beta)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert rate_id not in ids


@pytest.mark.asyncio
async def test_unbalanced_manual_journal_rejected(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    rows = accounts.json()["data"]
    cash = next(a for a in rows if a.get("code") == "1000")
    expense = next(a for a in rows if a.get("code") == "6000")
    bad = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Unbalanced probe",
            "lines": [
                {"account_id": expense["id"], "debit": 10, "credit": 0},
                {"account_id": cash["id"], "debit": 0, "credit": 9},
            ],
        },
    )
    assert bad.status_code in {400, 422}
