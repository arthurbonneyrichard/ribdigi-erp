"""Alerts to the restaurant when a guest orders or books online: email, WhatsApp, and in-app."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import emailer
from app import sms as sms_svc
from app.config import settings
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_restaurant_site import _menu_item, _open_site

pytestmark = pytest.mark.asyncio


async def _ready(client, db_session, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "")
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _menu_item(ac, admin, "Jollof", 40, category="Mains")
    await _open_site(ac, admin)
    emailer.clear_dev_outbox()
    sms_svc.clear_dev_outbox()
    return ac, admin, dish


async def test_settings_roundtrip_and_validation(client, db_session, monkeypatch):
    ac, admin, _dish = await _ready(client, db_session, monkeypatch)
    saved = await ac.put(
        "/api/v1/restaurant/alerts",
        headers=admin,
        json={"emails": ["Owner@Example.com", "owner@example.com", "chef@example.com"], "whatsapp": "+233241112233"},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()["data"]
    assert body["emails"] == ["owner@example.com", "chef@example.com"]
    assert body["whatsapp"] == "+233241112233" and body["orders"] is True and body["bookings"] is True
    assert (await ac.get("/api/v1/restaurant/alerts", headers=admin)).json()["data"]["whatsapp"] == "+233241112233"
    bad = await ac.put("/api/v1/restaurant/alerts", headers=admin, json={"whatsapp_template": "not-a-template"})
    assert bad.status_code == 422, bad.text
    too_many = await ac.put(
        "/api/v1/restaurant/alerts", headers=admin, json={"emails": [f"a{i}@example.com" for i in range(6)]}
    )
    assert too_many.status_code == 422, too_many.text


async def test_online_order_and_booking_alert_the_restaurant(client, db_session, monkeypatch):
    ac, admin, dish = await _ready(client, db_session, monkeypatch)
    await ac.put(
        "/api/v1/restaurant/alerts",
        headers=admin,
        json={"emails": ["owner@example.com"], "whatsapp": "+233241112233"},
    )
    order = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "pickup", "customer_name": "Ama", "phone": "+233201234567",
              "allergy": "Peanuts", "lines": [{"product_id": dish["id"], "quantity": 2}]},
    )
    assert order.status_code == 200, order.text
    mails = [row for row in emailer.get_dev_outbox() if "owner@example.com" in str(row.get("to"))]
    assert mails, emailer.get_dev_outbox()
    assert "New online order" in mails[-1]["subject"]
    assert "Peanuts" in mails[-1]["text_body"] and "Ama" in mails[-1]["text_body"]
    chats = [row for row in sms_svc.get_dev_outbox() if row.get("channel") == "whatsapp"]
    assert chats and chats[-1]["to"] == "whatsapp:+233241112233"
    assert "2× Jollof" in chats[-1]["body"]

    emailer.clear_dev_outbox()
    when = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0).isoformat()
    booked = await ac.post(
        "/api/v1/public/restaurant-site/alpha/book",
        json={"guest_name": "Kojo", "phone": "+233241112233", "party_size": 4, "booked_for": when},
    )
    assert booked.status_code == 200, booked.text
    mails = [row for row in emailer.get_dev_outbox() if "owner@example.com" in str(row.get("to"))]
    assert mails and "New table booking" in mails[-1]["subject"] and "Kojo" in mails[-1]["text_body"]

    notes = await ac.get("/api/v1/notifications", headers=admin)
    titles = [row["title"] for row in notes.json()["data"]]
    assert any(t.startswith("New online order") for t in titles)
    assert "New table booking" in titles


async def test_switches_and_failures_never_block_guests(client, db_session, monkeypatch):
    ac, admin, dish = await _ready(client, db_session, monkeypatch)
    await ac.put(
        "/api/v1/restaurant/alerts",
        headers=admin,
        json={"emails": ["owner@example.com"], "whatsapp": "+233241112233", "orders": False},
    )
    quiet = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "pickup", "customer_name": "Ama", "phone": "+233201234567",
              "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert quiet.status_code == 200, quiet.text
    assert not emailer.get_dev_outbox() and not sms_svc.get_dev_outbox()

    async def boom(*_a, **_k):
        raise RuntimeError("mail server is down")

    monkeypatch.setattr(emailer, "send_email", boom)
    await ac.put("/api/v1/restaurant/alerts", headers=admin, json={"orders": True})
    still = await ac.post(
        "/api/v1/public/restaurant-site/alpha/order",
        json={"service": "pickup", "customer_name": "Kwame", "phone": "+233201234568",
              "lines": [{"product_id": dish["id"], "quantity": 1}]},
    )
    assert still.status_code == 200, still.text


async def test_test_button_reports_each_channel(client, db_session, monkeypatch):
    ac, admin, _dish = await _ready(client, db_session, monkeypatch)
    await ac.put(
        "/api/v1/restaurant/alerts",
        headers=admin,
        json={"emails": ["owner@example.com"], "whatsapp": "+233241112233"},
    )
    result = await ac.post("/api/v1/restaurant/alerts/test", headers=admin)
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["email"]["sent"] is True and data["whatsapp"]["sent"] is True
