"""BR-7.2 quotation expiry reminders and auto-expire scan."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.notifications import DEFAULT_PREFERENCES, scan_quotation_expiry
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_quotation_expiry_in_default_preferences():
    assert "quotation_expiry" in DEFAULT_PREFERENCES
    assert DEFAULT_PREFERENCES["quotation_expiry"]["dashboard"] is True


@pytest.mark.asyncio
async def test_scan_quotation_expiry_reminds_and_marks_expired(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Expiry Quote Buyer", "credit_limit": 500},
    )
    customer_id = cust.json()["data"]["id"]

    soon = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": customer_id,
            "valid_days": 1,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert soon.status_code == 200, soon.text
    soon_id = soon.json()["data"]["id"]
    soon_number = soon.json()["data"]["quotation_number"]

    past = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": customer_id,
            "valid_days": 14,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert past.status_code == 200, past.text
    past_id = past.json()["data"]["id"]
    past_number = past.json()["data"]["quotation_number"]

    db_session.expire_all()
    soon_row = (
        await db_session.execute(select(m.SalesQuotation).where(m.SalesQuotation.id == soon_id))
    ).scalar_one()
    past_row = (
        await db_session.execute(select(m.SalesQuotation).where(m.SalesQuotation.id == past_id))
    ).scalar_one()
    # Within 1-day reminder window
    soon_row.valid_until = datetime.utcnow() + timedelta(hours=12)
    # Already past validity
    past_row.valid_until = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    scan = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scan.status_code == 200, scan.text
    body = scan.json()["data"]
    assert body["quotation_expiry"]["reminded"] >= 2
    assert body["quotation_expiry"]["expired"] >= 1

    db_session.expire_all()
    past_after = (
        await db_session.execute(select(m.SalesQuotation).where(m.SalesQuotation.id == past_id))
    ).scalar_one()
    assert past_after.status == "expired"

    notes = await ac.get("/api/v1/notifications?status=unread", headers=headers)
    assert notes.status_code == 200, notes.text
    messages = " ".join(n["message"] for n in notes.json()["data"])
    assert soon_number in messages
    assert past_number in messages
    assert any(n["category"] == "quotation_expiry" for n in notes.json()["data"])

    # Idempotent: second scan does not duplicate unread reminders
    again = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["quotation_expiry"]["reminded"] == 0


@pytest.mark.asyncio
async def test_scan_quotation_expiry_unit_skips_far_future(db_session, seeded):
    tenant_id = seeded["t1"].id
    customer = seeded["party1"]
    quote = m.SalesQuotation(
        tenant_id=tenant_id,
        quotation_number="Q-FAR",
        customer_id=customer.id,
        status="sent",
        subtotal=10,
        tax_amount=0,
        discount_amount=0,
        total_amount=10,
        valid_until=datetime.utcnow() + timedelta(days=10),
    )
    db_session.add(quote)
    await db_session.commit()

    result = await scan_quotation_expiry(db_session, tenant_id, within_days=1)
    await db_session.commit()
    assert result["reminded"] == 0
    assert result["expired"] == 0
