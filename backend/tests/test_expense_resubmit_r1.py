"""Rejected expense resubmit + submitter decision notifications."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import emailer
from app import expenses as expenses_svc
from app import models as m
from app.notifications import DEFAULT_PREFERENCES
from tests.conftest import auth_headers

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_expense_decision_pref_default_on():
    assert DEFAULT_PREFERENCES["expense_decision"]["dashboard"] is True
    assert DEFAULT_PREFERENCES["expense_decision"]["email"] is True


def test_resubmit_api_and_ui_surface():
    api = (BACKEND / "app" / "api.py").read_text(encoding="utf-8")
    assert '@api.post("/expenses/{expense_id}/resubmit")' in api
    svc = (BACKEND / "app" / "expenses.py").read_text(encoding="utf-8")
    assert "async def resubmit_expense" in svc
    assert "notify_expense_submitter" in svc

    expenses_ui = REPO / "frontend" / "app" / "expenses" / "page.tsx"
    dash_ui = REPO / "frontend" / "app" / "dashboard" / "page.tsx"
    if expenses_ui.exists():
        expenses = expenses_ui.read_text(encoding="utf-8")
        assert "/expenses/${id}/resubmit" in expenses
        assert "Resubmit" in expenses
    if dash_ui.exists():
        dash = dash_ui.read_text(encoding="utf-8")
        assert "expense_rejected" in dash
        assert "/expenses?status=rejected" in dash
        assert "expense_approved" in dash
        assert "/expenses?status=approved" in dash


@pytest.mark.asyncio
async def test_reject_notifies_submitter_then_resubmit_reopens(client, db_session, monkeypatch):
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    tenant_id = seed["t1"].id

    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Supplies",
            "amount": 250,
            "payment_method": "cash",
            "description": "R1 resubmit candidate",
            "payee": "Office Co",
        },
    )
    assert created.status_code == 200, created.text
    expense = created.json()["data"]
    eid = expense["id"]
    assert expense["status"] == "pending"

    rejected = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=mgr_h,
        json={"reason": "Missing receipt — please attach PDF"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "rejected"

    notes = await ac.get("/api/v1/notifications", headers=super_h)
    assert notes.status_code == 200, notes.text
    decision = [
        n
        for n in notes.json()["data"]
        if n.get("entity_id") == eid and n.get("category") == "expense_decision"
    ]
    assert decision, "submitter expense_decision notify missing on reject"
    assert decision[0]["title"] == "Expense Rejected"
    assert "Missing receipt" in (decision[0].get("message") or "")
    assert decision[0].get("entity_type") == "expense_rejected"

    outbox = emailer.get_dev_outbox()
    emailed: list[str] = []
    for o in outbox:
        to = o.get("to") or []
        emailed.extend([to] if isinstance(to, str) else list(to))
    assert seed["super"].email in emailed
    assert any("Expense Rejected" in (o.get("subject") or "") for o in outbox)

    resubmitted = await ac.post(
        f"/api/v1/expenses/{eid}/resubmit",
        headers=super_h,
        json={"comment": "Receipt attached — please re-review"},
    )
    # First call above expected 409 only if status was not rejected. Re-read after reject.
    assert resubmitted.status_code == 200, resubmitted.text
    body = resubmitted.json()["data"]
    assert body["status"] == "pending"
    assert body.get("rejection_reason") in (None, "")
    assert int(body["approval_step"]) == 1
    assert any(
        a.get("action") == "resubmit" and "Receipt attached" in (a.get("comment") or "")
        for a in body.get("approval_actions") or []
    )

    mgr_notes = await ac.get("/api/v1/notifications", headers=mgr_h)
    assert mgr_notes.status_code == 200, mgr_notes.text
    assert any(
        n.get("category") == "expense_approval"
        and n.get("entity_id") == eid
        and "resubmitted" in (n.get("message") or "").lower()
        for n in mgr_notes.json()["data"]
    )

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.entity_id == eid,
                m.AuditLog.action == "expense_resubmitted",
            )
        )
    ).scalars().all()
    assert audits

    again = await ac.post(
        f"/api/v1/expenses/{eid}/resubmit",
        headers=super_h,
        json={"comment": "again"},
    )
    assert again.status_code == 409
    assert "rejected" in (again.json().get("detail") or "").lower() or "rejected" in again.text.lower()

    approved = await ac.post(
        f"/api/v1/expenses/{eid}/approve",
        headers=mgr_h,
        json={"comment": "R1 approved after resubmit"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    after = await ac.get("/api/v1/notifications", headers=super_h)
    assert any(
        n.get("entity_id") == eid
        and n.get("category") == "expense_decision"
        and n.get("title") == "Expense Approved"
        for n in after.json()["data"]
    )

    approved_again = await ac.post(
        f"/api/v1/expenses/{eid}/resubmit",
        headers=super_h,
        json={"comment": "too late"},
    )
    assert approved_again.status_code == 409


@pytest.mark.asyncio
async def test_resubmit_under_threshold_auto_approves(client, db_session):
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)

    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Utilities",
            "amount": 250,
            "payment_method": "bank_transfer",
            "description": "R1 auto after resubmit",
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]

    rejected = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=mgr_h,
        json={"reason": "Amount too high"},
    )
    assert rejected.status_code == 200, rejected.text

    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=super_h,
        json={"expense_approval_threshold": 500, "expense_l2_threshold": 2000},
    )
    assert settings.status_code == 200, settings.text

    resubmitted = await ac.post(
        f"/api/v1/expenses/{eid}/resubmit",
        headers=super_h,
        json={"comment": "Threshold raised"},
    )
    assert resubmitted.status_code == 200, resubmitted.text
    data = resubmitted.json()["data"]
    assert data["status"] == "approved"
    assert any(a.get("action") == "auto_approve" for a in data.get("approval_actions") or [])


@pytest.mark.asyncio
async def test_resubmit_foreign_tenant_blocked(client):
    ac, seed = client
    super_h = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={"category": "Misc", "amount": 180, "payment_method": "cash", "description": "iso"},
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]

    mgr_h = await _mgr(ac)
    rejected = await ac.post(
        f"/api/v1/expenses/{eid}/reject",
        headers=mgr_h,
        json={"reason": "iso reject"},
    )
    assert rejected.status_code == 200, rejected.text

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    cross = await ac.post(
        f"/api/v1/expenses/{eid}/resubmit",
        headers=beta,
        json={"comment": "cross tenant"},
    )
    assert cross.status_code in (403, 404)


@pytest.mark.asyncio
async def test_service_reject_excludes_actor_from_submitter_notify(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 100
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        amount=250,
        category="Supplies",
        description="Manager own reject",
        payment_method="cash",
    )
    await expenses_svc.reject_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        expense_id=expense.id,
        reason="Self decision",
        actor_role="store_manager",
    )
    await db_session.commit()

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "expense_decision",
                m.Notification.entity_id == expense.id,
            )
        )
    ).scalars().all()
    assert not notes
