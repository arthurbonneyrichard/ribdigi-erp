"""Recurring Skip-next reason honesty (BR-9.5) — FE + API require reason (audit-only)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_recurring_skip_reason_ui_wired():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "skipNextReason" in page
    assert "Enter a skip reason before skipping the next occurrence" in page
    assert "Required before Skip next" in page
    assert 'aria-label="Skip next reason"' in page
    assert "JSON.stringify({ reason })" in page
    assert "/expenses/recurring/${id}/skip-next" in page
    assert "recurring_expense_skipped" in page
    # Skip-next must not post an empty body anymore.
    skip_fn = page.split("async function skipNextRecurring")[1].split("async function ")[0]
    assert "body: '{}'" not in skip_fn
    assert "{ reason }" in skip_fn
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "RecurringSkipReasonValue" in agents


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_skip_next_requires_reason_and_audits(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 40,
            "frequency": "weekly",
            "description": "Keep template text intact",
            "payee": "Skip Reason Co",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    rid = body["id"]
    before = body["next_run_at"]
    before_desc = body["description"]

    missing = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=headers,
        json={"reason": "   "},
    )
    # OpenAPI honesty: strip + RecurringSkipReasonValue → 422 (was service 400).
    assert blank.status_code == 422

    garbage = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422

    skipped = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=headers,
        json={"reason": "Holiday cycle — API hello-world"},
    )
    assert skipped.status_code == 200, skipped.text
    after = skipped.json()["data"]
    assert after["next_run_at"] > before
    assert after["description"] == before_desc

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "recurring_expense_skipped",
                m.AuditLog.entity_id == rid,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Holiday cycle — API hello-world"
    assert audit.details.get("previous_next_run_at")
    assert audit.details.get("next_run_at")
