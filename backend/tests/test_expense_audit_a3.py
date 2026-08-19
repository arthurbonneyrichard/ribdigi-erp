"""Stage 14 A3: finance domain audit for expense submit/approve/reject/auto-approve."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import audit as audit_svc
from app import expenses as expenses_svc
from app import models as m
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expense_auto_approve_and_reject_audited(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 100
    await db_session.flush()

    auto = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["mgr1"].id,
        amount=25,
        category="General",
        description="Petty cash auto",
        payment_method="cash",
    )
    assert auto.status == "approved"

    pending = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["u1"].id,
        amount=250,
        category="General",
        description="Needs reject",
        payment_method="cash",
    )
    assert pending.status == "pending"

    await expenses_svc.reject_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["mgr1"].id,
        expense_id=pending.id,
        reason="Missing receipt",
        actor_role="store_manager",
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)

    auto_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "expense_auto_approved"},
    )
    assert auto_logs.status_code == 200, auto_logs.text
    arow = next(r for r in auto_logs.json()["data"] if r["entity_id"] == auto.id)
    assert arow["integrity_hash"]
    assert arow["module"] == "expenses"
    assert float(arow["details"]["amount"]) == pytest.approx(25)

    submitted = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "expense_submitted"},
    )
    assert submitted.status_code == 200
    srow = next(r for r in submitted.json()["data"] if r["entity_id"] == pending.id)
    assert srow["module"] == "expenses"

    rejected = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "expense_rejected"},
    )
    assert rejected.status_code == 200
    rrow = next(r for r in rejected.json()["data"] if r["entity_id"] == pending.id)
    assert rrow["integrity_hash"]
    assert rrow["details"]["reason"] == "Missing receipt"

    journals = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "journal_posted"},
    )
    assert journals.status_code == 200
    assert any(
        (r.get("details") or {}).get("source_type") == "expense"
        and (r.get("details") or {}).get("source_id") == auto.id
        for r in journals.json()["data"]
    )

    chain = await audit_svc.verify_chain(db_session, tenant_id)
    assert chain["valid"] is True


@pytest.mark.asyncio
async def test_expense_level_and_final_approve_audited(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    tenant = await db_session.get(m.Tenant, tenant_id)
    await expenses_svc.update_approval_settings(
        db_session,
        tenant,
        levels=[
            {"min_amount": 100, "roles": ["store_manager"], "label": "Manager"},
            {"min_amount": 1000, "roles": ["company_admin"], "label": "Admin"},
        ],
    )
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["u1"].id,
        amount=1500,
        category="Travel",
        description="Multi-level audit",
        payment_method="cash",
    )
    assert expense.approval_steps_required == 2

    await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["mgr1"].id,
        expense_id=expense.id,
        actor_role="store_manager",
        comment="L1 ok",
    )
    assert expense.status == "pending"

    await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        expense_id=expense.id,
        actor_role="company_admin",
        comment="L2 ok",
    )
    assert expense.status == "approved"
    await db_session.commit()

    headers = await _super_headers(ac, seed)

    level = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "expense_level_approved"},
    )
    assert level.status_code == 200
    lrow = next(r for r in level.json()["data"] if r["entity_id"] == expense.id)
    assert lrow["module"] == "expenses"
    assert lrow["details"]["step"] == 1
    assert lrow["details"]["next_step"] == 2

    final = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "expense_approved"},
    )
    assert final.status_code == 200
    frow = next(r for r in final.json()["data"] if r["entity_id"] == expense.id)
    assert frow["integrity_hash"]
    assert frow["details"]["steps"] == 2

    # Final approve posts GL
    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == expense.id,
            )
        )
    ).scalar_one()
    assert je.status == "posted"

    journals = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "journal_posted"},
    )
    assert any(
        (r.get("details") or {}).get("source_id") == expense.id
        and (r.get("details") or {}).get("source_type") == "expense"
        for r in journals.json()["data"]
    )
