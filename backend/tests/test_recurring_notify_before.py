"""Recurring expense advance notification (BR-9.5)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import notifications as notifications_svc
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_scan_recurring_expense_due_notifies_and_dedupes(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)

    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 80,
            "frequency": "monthly",
            "description": "Notify rent",
            "payee": "Notify Landlord",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    row = await db_session.get(m.RecurringExpense, rid)
    assert row is not None
    # T−1 window: due in ~12 hours
    row.next_run_at = datetime.utcnow() + timedelta(hours=12)
    await db_session.commit()

    first = await notifications_svc.scan_recurring_expense_due(
        db_session, seed["t1"].id, within_days=1
    )
    await db_session.commit()
    assert first == 1

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "recurring_expense_due",
                m.Notification.entity_id == rid,
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert notes[0].title == "Recurring expense due soon"
    assert "Notify rent" in (notes[0].message or "") or "Notify Landlord" in (
        notes[0].message or ""
    ) or "80" in (notes[0].message or "")

    second = await notifications_svc.scan_recurring_expense_due(
        db_session, seed["t1"].id, within_days=1
    )
    await db_session.commit()
    assert second == 0

    notes[0].status = "read"
    row.next_run_at = datetime.utcnow() - timedelta(hours=1)
    await db_session.commit()

    third = await notifications_svc.scan_recurring_expense_due(
        db_session, seed["t1"].id, within_days=1
    )
    await db_session.commit()
    assert third == 1
    titles = (
        await db_session.execute(
            select(m.Notification.title).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "recurring_expense_due",
                m.Notification.entity_id == rid,
            )
        )
    ).scalars().all()
    assert "Recurring expense due" in titles

    settings = await ac.get("/api/v1/notifications/settings", headers=headers)
    assert settings.status_code == 200
    assert "recurring_expense_due" in (settings.json()["data"] or {})

    scanned = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scanned.status_code == 200, scanned.text
    body = scanned.json()["data"]
    assert "recurring_expense_due" in body
    assert "quotation_expiry" in body
    assert "payment_due" in body
