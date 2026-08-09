"""BR-9.3 expense approval email notifications to eligible approvers."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import emailer
from app import expenses as expenses_svc
from app import models as m
from app.notifications import DEFAULT_PREFERENCES


def test_expense_approval_email_default_on():
    assert DEFAULT_PREFERENCES["expense_approval"]["email"] is True


@pytest.mark.asyncio
async def test_pending_expense_notifies_approvers_by_role(db_session, seeded, monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 100
    tenant.expense_l2_threshold = 1000
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=250,
        category="Supplies",
        description="Needs manager approval",
        payment_method="cash",
    )
    assert expense.status == "pending"
    await db_session.commit()

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "expense_approval",
                m.Notification.entity_id == expense.id,
            )
        )
    ).scalars().all()
    recipient_ids = {n.user_id for n in notes}
    assert seeded["mgr1"].id in recipient_ids
    assert seeded["u1"].id not in recipient_ids  # submitter excluded
    assert all(n.user_id for n in notes)

    outbox = emailer.get_dev_outbox()
    assert any(o.get("to") == seeded["mgr1"].email or seeded["mgr1"].email in str(o) for o in outbox) or any(
        seeded["mgr1"].email in str(o.values()) for o in outbox
    )


@pytest.mark.asyncio
async def test_next_level_notifies_l2_roles(db_session, seeded, monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    await expenses_svc.update_approval_settings(
        db_session,
        tenant,
        levels=[
            {"min_amount": 50, "roles": ["store_manager"], "label": "L1"},
            {"min_amount": 500, "roles": ["company_admin", "super_admin"], "label": "L2"},
        ],
    )
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=800,
        category="Rent",
        description="Two-step",
        payment_method="bank_transfer",
    )
    assert expense.approval_steps_required == 2

    await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        expense_id=expense.id,
        comment="L1 ok",
        actor_role="store_manager",
    )
    await db_session.commit()

    l2_notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.entity_id == expense.id,
                m.Notification.title == "Expense Needs Next-Level Approval",
            )
        )
    ).scalars().all()
    assert l2_notes
    assert all(n.user_id != seeded["mgr1"].id for n in l2_notes)
    assert any(n.user_id == seeded["admin1"].id for n in l2_notes)
    assert any(n.user_id == seeded["super"].id for n in l2_notes)
