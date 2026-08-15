"""Quotation expiry notifications (BR-7.2)."""

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
async def test_scan_quotation_expiry_notifies_and_dedupes(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    created = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "valid_days": 14,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    qid = created.json()["data"]["id"]
    qnum = created.json()["data"]["quotation_number"]

    # Move validity into the T-1 window
    quote = await db_session.get(m.SalesQuotation, qid)
    assert quote is not None
    quote.valid_until = datetime.utcnow() + timedelta(hours=12)
    await db_session.commit()

    first = await notifications_svc.scan_quotation_expiry(db_session, seed["t1"].id, within_days=1)
    await db_session.commit()
    assert first == 1

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "quotation_expiry",
                m.Notification.entity_id == qid,
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert notes[0].title == "Quotation expiring soon"
    assert qnum in (notes[0].message or "")
    await db_session.refresh(quote)
    assert quote.status == "draft"  # T−1 window only notifies; does not expire yet

    second = await notifications_svc.scan_quotation_expiry(db_session, seed["t1"].id, within_days=1)
    await db_session.commit()
    assert second == 0

    # Past validity with unread T−1 still open → flip status without a second alert
    quote.valid_until = datetime.utcnow() - timedelta(hours=1)
    await db_session.commit()

    third = await notifications_svc.scan_quotation_expiry(db_session, seed["t1"].id, within_days=1)
    await db_session.commit()
    assert third == 0  # unread T−1 still dedupes notify
    await db_session.refresh(quote)
    assert quote.status == "expired"

    # Fresh past-due quote → notify "Quotation expired" + status expired
    created2 = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "valid_days": 14,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created2.status_code == 200, created2.text
    qid2 = created2.json()["data"]["id"]
    quote2 = await db_session.get(m.SalesQuotation, qid2)
    assert quote2 is not None
    quote2.status = "sent"
    quote2.valid_until = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    fourth = await notifications_svc.scan_quotation_expiry(db_session, seed["t1"].id, within_days=1)
    await db_session.commit()
    assert fourth == 1
    await db_session.refresh(quote2)
    assert quote2.status == "expired"
    titles = (
        await db_session.execute(
            select(m.Notification.title).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "quotation_expiry",
                m.Notification.entity_id == qid2,
            )
        )
    ).scalars().all()
    assert "Quotation expired" in titles

    # Reject of already-expired → 409
    rejected = await ac.post(f"/api/v1/sales/quotations/{qid2}/reject", headers=headers)
    assert rejected.status_code == 409

    settings = await ac.get("/api/v1/notifications/settings", headers=headers)
    assert settings.status_code == 200
    assert "quotation_expiry" in (settings.json()["data"] or {})

    scanned = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scanned.status_code == 200, scanned.text
    body = scanned.json()["data"]
    assert "quotation_expiry" in body
    assert "payment_due" in body
