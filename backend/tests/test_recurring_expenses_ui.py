"""Recurring expenses UI/API + EXP series on generate (BR-9.5 / BR-9.2 / BR-20.4)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_recurring_create_generate_exp_series_and_deactivate(client, seeded, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    year = datetime.utcnow().year

    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=admin,
        json={"expense_numbering": {"prefix": "EXP", "next_number": 77}},
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["data"]["expense_numbering"]["preview"] == f"EXP-{year}-0077"

    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 45.5,
            "frequency": "monthly",
            "description": "Office rent",
            "payment_method": "bank_transfer",
            "payee": "Landlord Co",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["frequency"] == "monthly"
    assert body["is_active"] is True
    assert body["amount"] == 45.5
    rid = body["id"]

    listed = await ac.get("/api/v1/expenses/recurring", headers=admin)
    assert listed.status_code == 200
    assert any(r["id"] == rid for r in listed.json()["data"])

    bad_freq = await ac.post(
        "/api/v1/expenses/recurring",
        headers=admin,
        json={"category_id": cat_id, "amount": 10, "frequency": "biweekly"},
    )
    assert bad_freq.status_code == 422

    gen = await ac.post("/api/v1/expenses/recurring/generate", headers=admin, json={})
    assert gen.status_code == 200, gen.text
    generated = gen.json()["data"]
    assert len(generated) >= 1
    hit = next(e for e in generated if e.get("payee") == "Landlord Co")
    assert hit["reference"] == f"EXP-{year}-0077"
    assert "recurring" in (hit.get("description") or "").lower()

    nxt = await ac.get("/api/v1/expenses/settings", headers=admin)
    assert nxt.json()["data"]["expense_numbering"]["preview"] == f"EXP-{year}-0078"

    # Next run advanced — generate again should create zero for this schedule.
    gen2 = await ac.post("/api/v1/expenses/recurring/generate", headers=admin, json={})
    assert gen2.status_code == 200
    assert not any(e.get("payee") == "Landlord Co" for e in gen2.json()["data"])

    deact = await ac.patch(
        f"/api/v1/expenses/recurring/{rid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    react = await ac.patch(
        f"/api/v1/expenses/recurring/{rid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    # Template edit (amount/payee) — future generates use new values
    edited = await ac.patch(
        f"/api/v1/expenses/recurring/{rid}",
        headers=admin,
        json={"amount": 99.0, "payee": "New Landlord", "description": "Office rent (updated)"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["amount"] == 99.0
    assert edited.json()["data"]["payee"] == "New Landlord"
    assert edited.json()["data"]["description"] == "Office rent (updated)"

    # Force due again and generate — new payee/amount on the new expense
    from app import models as m
    from sqlalchemy import select

    row = (
        await db_session.execute(select(m.RecurringExpense).where(m.RecurringExpense.id == rid))
    ).scalar_one()
    row.next_run_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    gen3 = await ac.post("/api/v1/expenses/recurring/generate", headers=admin, json={})
    assert gen3.status_code == 200, gen3.text
    hit2 = next(e for e in gen3.json()["data"] if e.get("payee") == "New Landlord")
    assert float(hit2["amount"]) == 99.0


@pytest.mark.asyncio
async def test_recurring_generate_respects_future_next_run(client, seeded, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 12,
            "frequency": "weekly",
            "description": "Future only",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    from app import models as m
    from sqlalchemy import select

    row = (
        await db_session.execute(select(m.RecurringExpense).where(m.RecurringExpense.id == rid))
    ).scalar_one()
    row.next_run_at = datetime.utcnow() + timedelta(days=7)
    await db_session.commit()

    gen = await ac.post("/api/v1/expenses/recurring/generate", headers=admin, json={})
    assert gen.status_code == 200
    assert not any(e.get("description", "").startswith("Future only") for e in gen.json()["data"])
