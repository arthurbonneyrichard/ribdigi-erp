"""Expense approval emails to matrix-step roles (BR-9.3)."""

from __future__ import annotations

import pytest

from app import emailer
from app import expenses as expenses_svc
from app import notifications as note_svc


def _outbox_recipients() -> set[str]:
    out: set[str] = set()
    for row in emailer.get_dev_outbox():
        to = row.get("to")
        if isinstance(to, list):
            out.update(str(x) for x in to)
        elif to:
            out.add(str(to))
    return out


@pytest.mark.asyncio
async def test_expense_approval_emails_current_step_roles(db_session, seeded, monkeypatch):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    emailer.clear_dev_outbox()

    tenant = seeded["t1"]
    tenant.expense_approval_threshold = 100
    tenant.expense_l2_threshold = 1000
    tenant.expense_approval_matrix = None
    await db_session.flush()

    # L1 default includes store_manager; L2 is company_admin/super_admin.
    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant.id,
        user_id=seeded["u1"].id,
        amount=1500,
        category="Supplies",
        description="Needs dual approval",
        payment_method="cash",
    )
    assert expense.status == "pending"
    assert expense.approval_steps_required == 2

    recipients1 = _outbox_recipients()
    assert "mgr@alpha.example.com" in recipients1
    assert "admin@alpha.example.com" in recipients1
    assert "super@alpha.example.com" in recipients1
    # Creator (cashier) must not be emailed as an approver
    assert "cashier@alpha.example.com" not in recipients1
    assert all("Expense Approval Required" in (m.get("subject") or "") for m in emailer.get_dev_outbox())

    emailer.clear_dev_outbox()
    mid = await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant.id,
        user_id=seeded["mgr1"].id,
        expense_id=expense.id,
        comment="L1 ok",
        actor_role="store_manager",
    )
    assert mid.status == "pending"
    assert mid.approval_step == 2

    recipients2 = _outbox_recipients()
    # L2 roles only (company_admin / super_admin) — not store_manager again
    assert "admin@alpha.example.com" in recipients2
    assert "super@alpha.example.com" in recipients2
    assert "mgr@alpha.example.com" not in recipients2
    assert all("Next-Level" in (m.get("subject") or "") for m in emailer.get_dev_outbox())


@pytest.mark.asyncio
async def test_expense_approval_email_respects_opt_out(db_session, seeded, monkeypatch):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    emailer.clear_dev_outbox()

    tenant = seeded["t1"]
    tenant.expense_approval_threshold = 50
    tenant.expense_l2_threshold = 10_000
    tenant.expense_approval_matrix = {
        "levels": [{"step": 1, "min_amount": 50, "roles": ["store_manager"], "label": "Manager"}]
    }
    await db_session.flush()

    await note_svc.update_preferences(
        db_session,
        tenant.id,
        seeded["mgr1"].id,
        {"expense_approval": {"dashboard": True, "email": False, "sms": False}},
    )

    await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant.id,
        user_id=seeded["u1"].id,
        amount=80,
        category="Travel",
        description="Opt-out check",
        payment_method="cash",
    )
    assert "mgr@alpha.example.com" not in _outbox_recipients()


@pytest.mark.asyncio
async def test_users_for_roles_helper(db_session, seeded):
    rows = await note_svc.users_for_roles(
        db_session, seeded["t1"].id, ["store_manager", "company_admin"]
    )
    emails = {u.email for u in rows}
    assert "mgr@alpha.example.com" in emails
    assert "admin@alpha.example.com" in emails
    assert "cashier@alpha.example.com" not in emails

    filtered = await note_svc.users_for_roles(
        db_session,
        seeded["t1"].id,
        ["store_manager"],
        exclude_user_ids={seeded["mgr1"].id},
    )
    assert filtered == []


def test_expense_approval_email_default_pref_on():
    prefs = note_svc.merge_preferences(None)
    assert prefs["expense_approval"]["email"] is True
    assert prefs["expense_approval"]["dashboard"] is True
