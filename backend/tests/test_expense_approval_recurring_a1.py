"""Stage 22 A1: Expense approval & recurring fidelity (BR-9.3, BR-9.5)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    import pyotp

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expense_approval_and_recurring_fidelity(client, db_session):
    """BR-9.3 thresholds/chain/comments/notify + BR-9.5 frequency/generate/notify/skip/modify."""
    ac, seed = client
    mgr_h = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id

    # --- BR-9.3: configurable thresholds / multi-level matrix ---
    # L2 uses super_admin (seeded company_admin lacks 2FA enrollment for approve paths).
    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=super_h,
        json={
            "levels": [
                {"min_amount": 100, "roles": ["store_manager"], "label": "L1 Manager"},
                {"min_amount": 1000, "roles": ["super_admin"], "label": "L2 Super"},
            ]
        },
    )
    assert settings.status_code == 200, settings.text
    sdata = settings.json()["data"]
    assert float(sdata["expense_approval_threshold"]) == pytest.approx(100)
    assert float(sdata["expense_l2_threshold"]) == pytest.approx(1000)
    assert len(sdata["levels"]) == 2

    got_settings = await ac.get("/api/v1/expenses/settings", headers=mgr_h)
    assert got_settings.status_code == 200
    assert len(got_settings.json()["data"]["levels"]) == 2

    # Super submits high amount (not an L1 actor) → pending, 2 steps, approver notified
    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Supplies",
            "amount": 1500,
            "payment_method": "bank_transfer",
            "description": "A1 multi-level purchase",
            "payee": "Office Depot",
            "reference": "A1-APPR-001",
        },
    )
    assert created.status_code == 200, created.text
    expense = created.json()["data"]
    eid = expense["id"]
    assert expense["status"] == "pending"
    assert int(expense["approval_steps_required"]) == 2
    assert int(expense["approval_step"]) == 1

    notes = await ac.get("/api/v1/notifications", headers=mgr_h)
    assert notes.status_code == 200, notes.text
    assert any(
        n.get("category") == "expense_approval" and n.get("entity_id") == eid
        for n in notes.json()["data"]
    ), "approver notify (expense_approval) missing"

    # L1 approve with comment
    l1 = await ac.post(
        f"/api/v1/expenses/{eid}/approve",
        headers=mgr_h,
        json={"comment": "A1 L1 approved — within budget"},
    )
    assert l1.status_code == 200, l1.text
    l1data = l1.json()["data"]
    assert l1data["status"] == "pending"
    assert int(l1data["approval_step"]) == 2
    assert any(
        a.get("step") == 1
        and a.get("action") == "approve"
        and "L1 approved" in (a.get("comment") or "")
        for a in l1data.get("approval_actions") or []
    )

    # L2 approve with comment (super_admin may finalize own submission)
    l2 = await ac.post(
        f"/api/v1/expenses/{eid}/approve",
        headers=super_h,
        json={"comment": "A1 L2 final ok"},
    )
    assert l2.status_code == 200, l2.text
    l2data = l2.json()["data"]
    assert l2data["status"] == "approved"
    actions = l2data.get("approval_actions") or []
    assert [a["action"] for a in actions] == ["approve", "approve"]
    assert [a["step"] for a in actions] == [1, 2]
    assert any("L2 final" in (a.get("comment") or "") for a in actions)

    # Rejection with comment/reason
    pending = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Misc",
            "amount": 250,
            "payment_method": "cash",
            "description": "A1 reject candidate",
        },
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["data"]["status"] == "pending"
    rid = pending.json()["data"]["id"]

    rejected = await ac.post(
        f"/api/v1/expenses/{rid}/reject",
        headers=mgr_h,
        json={"reason": "A1 missing receipt", "comment": "Please re-submit with PDF"},
    )
    assert rejected.status_code == 200, rejected.text
    rdata = rejected.json()["data"]
    assert rdata["status"] == "rejected"
    assert "missing receipt" in (rdata.get("rejection_reason") or "").lower() or (
        "missing receipt" in (rdata.get("approval_comment") or "").lower()
    )

    # --- BR-9.5: frequencies, auto-generate, notify-before, skip/modify ---
    freqs = ("daily", "weekly", "monthly", "yearly")
    created_ids: dict[str, str] = {}
    for freq in freqs:
        row = await ac.post(
            "/api/v1/expenses/recurring",
            headers=mgr_h,
            json={
                "category": "Utilities",
                "description": f"A1 {freq} utility",
                "amount": 40,
                "frequency": freq,
                "payment_method": "bank_transfer",
                "payee": "Utility Co",
            },
        )
        assert row.status_code == 200, row.text
        body = row.json()["data"]
        assert body["frequency"] == freq
        created_ids[freq] = body["id"]

    # Modify next occurrence on monthly template
    monthly_id = created_ids["monthly"]
    modified = await ac.patch(
        f"/api/v1/expenses/recurring/{monthly_id}",
        headers=mgr_h,
        json={"next_amount": 55.25, "next_description": "A1 monthly adjusted"},
    )
    assert modified.status_code == 200, modified.text
    assert float(modified.json()["data"]["next_amount"]) == pytest.approx(55.25)

    monthly = (
        await db_session.execute(
            select(m.RecurringExpense).where(m.RecurringExpense.id == monthly_id)
        )
    ).scalar_one()
    monthly.next_run_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    gen = await ac.post("/api/v1/expenses/recurring/generate", headers=mgr_h)
    assert gen.status_code == 200, gen.text
    generated = gen.json()["data"]
    assert any(
        float(e["amount"]) == pytest.approx(55.25)
        and e["description"] == "A1 monthly adjusted"
        for e in generated
    ), generated

    # Skip next on weekly template
    weekly_id = created_ids["weekly"]
    skip = await ac.patch(
        f"/api/v1/expenses/recurring/{weekly_id}",
        headers=mgr_h,
        json={"skip_next": True},
    )
    assert skip.status_code == 200
    assert skip.json()["data"]["skip_next"] is True

    weekly = (
        await db_session.execute(
            select(m.RecurringExpense).where(m.RecurringExpense.id == weekly_id)
        )
    ).scalar_one()
    weekly.next_run_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    before_refs = (
        await db_session.execute(
            select(m.Expense).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.reference == f"REC-{weekly_id[:8]}",
            )
        )
    ).scalars().all()

    gen_skip = await ac.post("/api/v1/expenses/recurring/generate", headers=mgr_h)
    assert gen_skip.status_code == 200
    after_refs = (
        await db_session.execute(
            select(m.Expense).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.reference == f"REC-{weekly_id[:8]}",
            )
        )
    ).scalars().all()
    assert len(after_refs) == len(before_refs)

    # Notify before auto-generation (scan-due)
    daily_id = created_ids["daily"]
    daily = (
        await db_session.execute(
            select(m.RecurringExpense).where(m.RecurringExpense.id == daily_id)
        )
    ).scalar_one()
    daily.next_run_at = datetime.utcnow() + timedelta(hours=6)
    daily.skip_next = False
    await db_session.commit()

    scan = await ac.post("/api/v1/notifications/scan-due", headers=mgr_h)
    assert scan.status_code == 200, scan.text
    assert scan.json()["data"]["recurring_expense"]["reminded"] >= 1

    mgr_notes = await ac.get("/api/v1/notifications", headers=mgr_h)
    assert any(
        n.get("category") == "recurring_expense" for n in mgr_notes.json()["data"]
    )


def test_br_9_3_9_5_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s93 = br.split("#### BR-9.3 Expense Approval")[1].split("#### BR-9.4")[0]
    assert "[x] Configurable approval thresholds" in s93
    assert "[x] Multi-level approval chain" in s93
    assert "[x] Approval/rejection with comments" in s93
    assert "[x] Email notification to approvers" in s93
    assert "Stage 22 A1" in s93
    assert "test_expense_approval_recurring_a1.py" in s93

    s95 = br.split("#### BR-9.5 Recurring Expenses")[1].split("---")[0]
    assert "[x] Set frequency (daily, weekly, monthly, yearly)" in s95
    assert "[x] Auto-generate expense entries" in s95
    assert "[x] Notification before auto-generation" in s95
    assert "[x] Skip or modify individual occurrences" in s95
    assert "Stage 22 A1" in s95

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    a1_line = [ln for ln in plan.splitlines() if "| **A1**" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_expense_approval_recurring_a1.py" in plan
