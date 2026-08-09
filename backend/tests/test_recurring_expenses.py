"""BR-9.5 recurring expense notify-before + skip/modify occurrences."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.notifications import DEFAULT_PREFERENCES, scan_recurring_expense_upcoming
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_recurring_expense_in_default_preferences():
    assert "recurring_expense" in DEFAULT_PREFERENCES
    assert DEFAULT_PREFERENCES["recurring_expense"]["dashboard"] is True


@pytest.mark.asyncio
async def test_skip_next_occurrence_does_not_create_expense(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category": "Utilities",
            "description": "Monthly power",
            "amount": 120,
            "frequency": "monthly",
            "payment_method": "bank_transfer",
            "payee": "ECG",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    row = (
        await db_session.execute(select(m.RecurringExpense).where(m.RecurringExpense.id == rid))
    ).scalar_one()
    row.next_run_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    skip = await ac.patch(
        f"/api/v1/expenses/recurring/{rid}",
        headers=headers,
        json={"skip_next": True},
    )
    assert skip.status_code == 200, skip.text
    assert skip.json()["data"]["skip_next"] is True

    before = (
        await db_session.execute(
            select(m.Expense).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.reference == f"REC-{rid[:8]}",
            )
        )
    ).scalars().all()

    gen = await ac.post("/api/v1/expenses/recurring/generate", headers=headers)
    assert gen.status_code == 200, gen.text
    assert gen.json()["data"] == []

    after = (
        await db_session.execute(
            select(m.Expense).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.reference == f"REC-{rid[:8]}",
            )
        )
    ).scalars().all()
    assert len(after) == len(before)

    await db_session.refresh(row)
    assert row.skip_next is False
    assert row.next_run_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_modify_next_occurrence_amount_and_description(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category": "Rent",
            "description": "Shop rent",
            "amount": 500,
            "frequency": "monthly",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/expenses/recurring/{rid}",
        headers=headers,
        json={"next_amount": 550.5, "next_description": "Shop rent + service charge"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["next_amount"] == 550.5
    assert patched.json()["data"]["amount"] == 500
    assert patched.json()["data"]["skip_next"] is False

    row = (
        await db_session.execute(select(m.RecurringExpense).where(m.RecurringExpense.id == rid))
    ).scalar_one()
    row.next_run_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    gen = await ac.post("/api/v1/expenses/recurring/generate", headers=headers)
    assert gen.status_code == 200, gen.text
    assert len(gen.json()["data"]) == 1
    expense = gen.json()["data"][0]
    assert expense["amount"] == 550.5
    assert expense["description"] == "Shop rent + service charge"

    await db_session.refresh(row)
    assert row.next_amount is None
    assert row.next_description is None
    assert float(row.amount) == 500.0


@pytest.mark.asyncio
async def test_scan_recurring_expense_upcoming_notifies_and_dedupes(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category": "Utilities",
            "description": "Internet",
            "amount": 80,
            "frequency": "monthly",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    row = (
        await db_session.execute(select(m.RecurringExpense).where(m.RecurringExpense.id == rid))
    ).scalar_one()
    row.next_run_at = datetime.utcnow() + timedelta(hours=12)
    await db_session.commit()

    scan = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scan.status_code == 200, scan.text
    body = scan.json()["data"]
    assert "recurring_expense" in body
    assert body["recurring_expense"]["reminded"] >= 1

    notes = await ac.get("/api/v1/notifications", headers=headers)
    assert notes.status_code == 200
    assert any(n["category"] == "recurring_expense" for n in notes.json()["data"])

    again = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert again.status_code == 200
    assert again.json()["data"]["recurring_expense"]["reminded"] == 0


@pytest.mark.asyncio
async def test_scan_skips_when_skip_next_set(db_session, seeded):
    tenant_id = seeded["t1"].id
    row = m.RecurringExpense(
        tenant_id=tenant_id,
        category="Misc",
        description="One-off skip",
        amount=10,
        frequency="weekly",
        next_run_at=datetime.utcnow() + timedelta(hours=6),
        is_active=True,
        skip_next=True,
    )
    db_session.add(row)
    await db_session.commit()

    result = await scan_recurring_expense_upcoming(db_session, tenant_id, within_days=1)
    assert result["reminded"] == 0
