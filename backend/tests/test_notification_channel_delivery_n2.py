"""Stage 16 N2: email/SMS channel delivery respects prefs; console attempts recorded."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import emailer
from app import models as m
from app import notifications as notifications_svc
from app import sms as sms_svc
from app.notifications import DEFAULT_PREFERENCES, update_preferences
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _outbox_emails() -> list[str]:
    emailed: list[str] = []
    for o in emailer.get_dev_outbox():
        to = o.get("to") or []
        if isinstance(to, str):
            emailed.append(to)
        else:
            emailed.extend(to)
    return emailed


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.fixture(autouse=True)
def _channel_console(monkeypatch):
    emailer.clear_dev_outbox()
    sms_svc.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    monkeypatch.setattr("app.sms.settings.SMS_ENABLED", True)
    monkeypatch.setattr("app.sms.settings.TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr("app.sms.settings.TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr("app.sms.settings.TWILIO_FROM_NUMBER", "")
    yield
    emailer.clear_dev_outbox()
    sms_svc.clear_dev_outbox()


def test_outline_categories_default_channels_off_for_email_sms():
    """Outline buckets keep email/SMS off by default (opt-in per user)."""
    for cat in ("low_stock", "new_order", "credit_limit", "purchase_received", "shift_variance", "transfer"):
        assert DEFAULT_PREFERENCES[cat]["dashboard"] is True
        assert DEFAULT_PREFERENCES[cat]["email"] is False
        assert DEFAULT_PREFERENCES[cat]["sms"] is False


@pytest.mark.asyncio
async def test_new_order_email_attempt_respects_prefs(client, db_session):
    """Important Sales Events: new_order → console email only for admins with email on."""
    ac, seed = client
    tenant_id = seed["t1"].id
    admin = seed["admin1"]
    super_u = seed["super"]

    await update_preferences(
        db_session,
        tenant_id,
        admin.id,
        {"new_order": {"dashboard": True, "email": True, "sms": False}},
    )
    await update_preferences(
        db_session,
        tenant_id,
        super_u.id,
        {"new_order": {"dashboard": True, "email": False, "sms": False}},
    )
    await db_session.commit()

    headers = await _mgr(ac)
    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 15,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["data"]["id"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == order_id,
            )
        )
    ).scalars().all()
    assert notes

    outbox = emailer.get_dev_outbox()
    assert outbox
    assert all(o.get("mode") == "console" for o in outbox)
    # Console attempt is not a carrier delivery receipt
    assert all("delivered" not in o for o in outbox)
    emailed = _outbox_emails()
    assert admin.email in emailed
    assert super_u.email not in emailed
    assert any("[RIBDIGI]" in (o.get("subject") or "") for o in outbox)
    assert any("new_order" in (o.get("text_body") or "") for o in outbox)


@pytest.mark.asyncio
async def test_low_stock_email_and_sms_attempts(client, db_session):
    """Low Stock: email + SMS console attempts when admin opts in (phone required for SMS)."""
    ac, seed = client
    tenant_id = seed["t1"].id
    admin = seed["admin1"]
    admin.phone = "+233241112233"
    await update_preferences(
        db_session,
        tenant_id,
        admin.id,
        {"low_stock": {"dashboard": True, "email": True, "sms": True}},
    )
    await db_session.commit()

    product = m.Product(
        tenant_id=tenant_id,
        name="S16 N2 Low Stock SKU",
        sku="S16-N2-LOW",
        cost_price=1,
        selling_price=2,
        stock_qty=2,
        reorder_level=10,
        minimum_stock=1,
    )
    db_session.add(product)
    await db_session.commit()

    created = await notifications_svc.scan_low_stock(db_session, tenant_id)
    await db_session.commit()
    assert created >= 1

    email_box = emailer.get_dev_outbox()
    assert email_box
    assert all(o.get("mode") == "console" for o in email_box)
    assert all("delivered" not in o for o in email_box)
    assert admin.email in _outbox_emails()
    assert any("Low Stock" in (o.get("subject") or "") or "low stock" in (o.get("subject") or "").lower() for o in email_box)

    sms_box = sms_svc.get_dev_outbox()
    assert sms_box
    assert all(o.get("mode") == "console" for o in sms_box)
    assert all("delivered" not in o for o in sms_box)
    assert any(o.get("to") == "+233241112233" for o in sms_box)
    assert any("RIBDIGI" in (o.get("body") or "") for o in sms_box)


@pytest.mark.asyncio
async def test_outline_category_email_off_skips_send(client, db_session):
    """Default email=False for new_order → dashboard note only, no email attempt."""
    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 9,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["data"]["id"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == order_id,
            )
        )
    ).scalars().all()
    assert notes
    assert emailer.get_dev_outbox() == []
    assert sms_svc.get_dev_outbox() == []


def test_notification_channel_n2_docs():
    plan = (ROOT / "docs/STAGE_16_PLAN.md").read_text(encoding="utf-8")
    assert "| **N2**" in plan
    assert "test_notification_channel_delivery_n2.py" in plan
    assert "COMPLETE" in plan
    manual = (ROOT / "docs/USER_MANUAL.md").read_text(encoding="utf-8")
    assert "Stage 16 N2" in manual
