"""Skip next recurring expense occurrence (BR-9.5)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _parse_dt(value: str) -> datetime:
    raw = value.replace("Z", "")
    if "+" in raw[10:] or raw.count("-") > 2:
        # strip timezone offset for naive compare
        for sep in ("+", "-"):
            idx = raw.find(sep, 10)
            if idx > 0:
                raw = raw[:idx]
                break
    return datetime.fromisoformat(raw)


@pytest.mark.asyncio
async def test_skip_next_advances_without_generating(client, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 99,
            "frequency": "weekly",
            "description": "Skip me rent",
            "payee": "Skip Landlord",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    rid = body["id"]
    before = body["next_run_at"]
    assert before

    skipped = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=admin,
        json={"reason": "Skip me rent — unit test"},
    )
    assert skipped.status_code == 200, skipped.text
    after = skipped.json()["data"]["next_run_at"]
    assert after
    assert after > before
    assert skipped.json()["data"]["is_active"] is True

    # Due generate must not create for this payee (next_run moved forward).
    gen = await ac.post("/api/v1/expenses/recurring/generate", headers=admin, json={})
    assert gen.status_code == 200, gen.text
    assert not any(e.get("payee") == "Skip Landlord" for e in gen.json()["data"])


@pytest.mark.asyncio
async def test_skip_next_inactive_and_missing(client, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=admin,
        json={"category_id": cat_id, "amount": 5, "frequency": "daily", "description": "pause"},
    )
    rid = created.json()["data"]["id"]

    deact = await ac.patch(
        f"/api/v1/expenses/recurring/{rid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200

    bad = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=admin,
        json={"reason": "should fail inactive"},
    )
    assert bad.status_code == 400

    missing = await ac.post(
        "/api/v1/expenses/recurring/00000000-0000-0000-0000-000000000000/skip-next",
        headers=admin,
        json={"reason": "should fail missing"},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_skip_next_from_overdue_next_run(client, seeded, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 20,
            "frequency": "monthly",
            "description": "Overdue skip",
            "payee": "Overdue Skip Co",
        },
    )
    rid = created.json()["data"]["id"]

    past = datetime.utcnow() - timedelta(days=40)
    row = (
        await db_session.execute(select(m.RecurringExpense).where(m.RecurringExpense.id == rid))
    ).scalar_one()
    row.next_run_at = past
    await db_session.commit()

    skipped = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=admin,
        json={"reason": "Catch up overdue — unit test"},
    )
    assert skipped.status_code == 200, skipped.text
    after = skipped.json()["data"]["next_run_at"]
    after_dt = _parse_dt(after)
    delta = after_dt - past
    assert timedelta(days=25) <= delta <= timedelta(days=35)
