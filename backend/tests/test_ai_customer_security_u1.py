"""Stage 20 U1: AI customer assistant + security monitor fidelity (BR-21.9–21.10)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import audit as audit_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _backdate_latest(db_session, tenant_id: str, when: datetime, *, action: str | None = None):
    q = select(m.AuditLog).where(m.AuditLog.tenant_id == tenant_id)
    if action:
        q = q.where(m.AuditLog.action == action)
    row = (
        await db_session.execute(q.order_by(m.AuditLog.created_at.desc()))
    ).scalars().first()
    row.created_at = when
    await db_session.flush()
    return row


async def _seed_customer_intel(db_session, seed):
    tenant_id = seed["t1"].id
    now = datetime.utcnow()
    for i in range(5):
        db_session.add(
            m.SalesInvoice(
                tenant_id=tenant_id,
                invoice_number=f"INV-U1-BEST-{i}",
                customer_id=seed["party1"].id,
                status="posted",
                subtotal=250,
                tax_amount=0,
                total_amount=250,
                paid_amount=250,
                created_at=now - timedelta(days=i * 2),
                posted_at=now - timedelta(days=i * 2),
            )
        )
    stale = m.Party(
        tenant_id=tenant_id,
        name="U1 Quiet Customer",
        kind="customer",
        status="active",
        credit_limit=40,
    )
    db_session.add(stale)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-U1-STALE",
            customer_id=stale.id,
            status="posted",
            subtotal=12,
            tax_amount=0,
            total_amount=12,
            paid_amount=12,
            created_at=now - timedelta(days=110),
            posted_at=now - timedelta(days=110),
        )
    )
    await db_session.commit()
    return stale


@pytest.mark.asyncio
async def test_customer_churn_best_promos_api(client, db_session):
    """BR-21.9: churn risk, best customers, promotion suggestions via insights API."""
    ac, seed = client
    headers = await _mgr(ac)
    stale = await _seed_customer_intel(db_session, seed)

    r = await ac.get(
        "/api/v1/ai/customers/insights",
        headers=headers,
        params={"lookback_days": 180},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["customer_count"] >= 2

    assert body["best_customers"]
    assert body["best_customers"][0]["customer_id"] == seed["party1"].id
    assert body["best_customers"][0]["monetary"] >= 1000
    assert "churn" in body["best_customers"][0]
    assert body["best_customers"][0]["churn"]["score"] >= 0

    churn_ids = {c["customer_id"] for c in body["churn_risks"]}
    assert stale.id in churn_ids
    stale_row = next(c for c in body["churn_risks"] if c["customer_id"] == stale.id)
    assert stale_row["churn"]["band"] in {"high", "medium"}
    assert stale_row["churn"]["score"] >= 35

    assert body["promotion_suggestions"]
    promo = body["promotion_suggestions"][0]
    assert promo["type"] in {"win_back", "re_engage", "vip", "upsell"}
    assert promo["suggestion"]
    assert "Beta" not in " ".join(c.get("name") or "" for c in body["best_customers"])

    assist = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "Who are my best customers?"},
    )
    assert assist.status_code == 200, assist.text
    adata = assist.json()["data"]
    assert adata.get("best_customers") or "Alpha" in (adata.get("answer") or "")


@pytest.mark.asyncio
async def test_security_login_txn_alerts_and_notify(client, db_session):
    """BR-21.10: unusual login (IP/device), txn burst, admin notify via alerts API."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    user = seed["mgr1"]
    now = datetime.utcnow()

    # Historical daytime logins from known IP/device
    for days_ago in (12, 10, 8, 6, 4):
        await audit_svc.record_event(
            db_session,
            tenant_id=tenant_id,
            user_id=user.id,
            module="auth",
            action="login",
            entity="user",
            entity_id=user.id,
            details={},
            ip_address="10.0.0.20",
            user_agent="AlphaBrowser/1.0",
        )
        await _backdate_latest(
            db_session,
            tenant_id,
            now - timedelta(days=days_ago, hours=3),
            action="login",
        )

    # New IP + device login (recent)
    await audit_svc.record_event(
        db_session,
        tenant_id=tenant_id,
        user_id=user.id,
        module="auth",
        action="login",
        entity="user",
        entity_id=user.id,
        details={},
        ip_address="203.0.113.77",
        user_agent="StrangeClient/9.9",
    )
    await _backdate_latest(db_session, tenant_id, now - timedelta(minutes=5), action="login")

    # Suspicious sensitive transaction burst
    for i in range(9):
        await audit_svc.record_event(
            db_session,
            tenant_id=tenant_id,
            user_id=user.id,
            module="sales",
            action="post",
            entity="sales_invoice",
            entity_id=f"inv-u1-{i}",
            details={},
            ip_address="203.0.113.77",
            user_agent="StrangeClient/9.9",
        )
        await _backdate_latest(
            db_session,
            tenant_id,
            now - timedelta(minutes=10 - i),
            action="post",
        )
    await db_session.commit()

    r = await ac.get(
        "/api/v1/ai/security/alerts",
        headers=headers,
        params={"lookback_hours": 48, "notify": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rules_v1"
    assert body["alert_count"] >= 1
    kinds = {a["kind"] for a in body["alerts"]}
    assert "unusual_login_ip" in kinds
    assert "unusual_login_device" in kinds
    assert "suspicious_transaction_burst" in kinds
    assert body["high_or_critical_count"] >= 1
    assert any(a["severity"] in {"high", "critical", "medium"} for a in body["alerts"])
    assert body["notifications_created"] >= 1

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "security",
            )
        )
    ).scalars().all()
    assert notes
    assert any(n.status == "unread" for n in notes)
    blob = str(body)
    assert "Beta" not in blob
    assert "198.51.100" not in blob


def test_br_21_9_10_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s219 = br.split("#### BR-21.9 AI Customer Assistant (Basic)")[1].split("#### BR-21.10")[0]
    assert "[x] Customer churn risk scoring" in s219
    assert "[x] Best customer identification" in s219
    assert "[x] Personalized promotion suggestions" in s219
    assert "Stage 20 U1" in s219
    assert "test_ai_customer_security_u1.py" in s219

    s2110 = br.split("#### BR-21.10 AI Security Monitor (Basic)")[1].split("---")[0]
    assert "[x] Detect unusual login patterns" in s2110
    assert "[x] Flag suspicious transaction patterns" in s2110
    assert "[x] Alert admins on potential fraud indicators" in s2110
    assert "Stage 20 U1" in s2110

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    u1_line = [ln for ln in plan.splitlines() if "| **U1**" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_ai_customer_security_u1.py" in plan
