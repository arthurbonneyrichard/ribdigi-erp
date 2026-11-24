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


# ---- the same alerts for the online shop and the hotel ----

from tests.test_ecommerce_r1 import _login_admin, _seed_storefront  # noqa: E402
from tests.test_hotel_audit_2026_11 import _hotel, _open_booking, _request, _room  # noqa: E402


async def test_online_shop_order_alerts_the_shop(client, db_session, seeded, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    admin = await _login_admin(ac)
    saved = await ac.put(
        "/api/v1/online-alerts", headers=admin, json={"emails": ["shop@example.com"], "whatsapp": "+233241112233"}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["industry"] == "retail"
    storefront, _warehouse, _store = await _seed_storefront(db_session, seed, buffer=0, stock=10)
    preview = storefront.preview_token
    cart = (await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")).json()["data"]["token"]
    await ac.post(
        f"/api/v1/storefront/cart/{cart}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 2},
    )
    emailer.clear_dev_outbox()
    sms_svc.clear_dev_outbox()
    placed = await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        json={"cart_token": cart, "guest_name": "Ama Guest", "guest_email": "ama@example.com",
              "guest_phone": "+233201234567", "fulfillment": "delivery", "delivery_address": "12 Market Street Accra"},
    )
    assert placed.status_code == 200, placed.text
    mails = [row for row in emailer.get_dev_outbox() if "shop@example.com" in str(row.get("to"))]
    assert mails and "New shop order" in mails[-1]["subject"]
    assert "12 Market Street" in mails[-1]["text_body"] and "Ama Guest" in mails[-1]["text_body"]
    chats = [row for row in sms_svc.get_dev_outbox() if row.get("channel") == "whatsapp"]
    assert chats and chats[-1]["to"] == "whatsapp:+233241112233"


async def test_hotel_stay_request_alerts_the_hotel(client, db_session, seeded, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    h = await _hotel(ac, seed, db_session)
    slug = await _open_booking(ac, h, db_session, seed)
    saved = await ac.put("/api/v1/online-alerts", headers=h, json={"emails": ["front@example.com"]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["industry"] == "hotel"
    emailer.clear_dev_outbox()
    placed = await ac.post(f"/api/v1/public/hotel-booking/{slug}", json=_request(await _room(ac, h), nights=2))
    assert placed.status_code == 200, placed.text
    mails = [row for row in emailer.get_dev_outbox() if "front@example.com" in str(row.get("to"))]
    assert mails and "New stay request" in mails[-1]["subject"]
    assert "2 nights" in mails[-1]["text_body"] and "Ama Boateng" in mails[-1]["text_body"]
    test = await ac.post("/api/v1/online-alerts/test", headers=h)
    assert test.status_code == 200 and test.json()["data"]["email"]["sent"] is True


async def test_company_can_add_its_own_browser_icon(client, db_session, monkeypatch):
    import io

    from PIL import Image

    ac, admin, _dish = await _ready(client, db_session, monkeypatch)
    page = (await ac.get("/api/v1/public/restaurant-site/alpha")).json()["data"]
    assert page["favicon_version"] is None
    assert (await ac.get("/api/v1/public/restaurant-site/alpha/favicon")).status_code == 404

    buf = io.BytesIO()
    Image.new("RGBA", (600, 600), (200, 30, 30, 255)).save(buf, "PNG")
    up = await ac.post(
        "/api/v1/online-alerts/favicon", headers=admin, files={"file": ("icon.png", buf.getvalue(), "image/png")}
    )
    assert up.status_code == 200, up.text
    page = (await ac.get("/api/v1/public/restaurant-site/alpha")).json()["data"]
    assert page["favicon_version"]
    icon = await ac.get("/api/v1/public/restaurant-site/alpha/favicon")
    assert icon.status_code == 200 and icon.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(icon.content)).size == (256, 256)  # shrunk to icon size
    assert (await ac.get("/api/v1/online-alerts/favicon", headers=admin)).status_code == 200
    assert (await ac.get("/api/v1/online-alerts", headers=admin)).json()["data"]["has_favicon"] is True

    gone = await ac.delete("/api/v1/online-alerts/favicon", headers=admin)
    assert gone.status_code == 200, gone.text
    assert (await ac.get("/api/v1/public/restaurant-site/alpha/favicon")).status_code == 404
    bad = await ac.post(
        "/api/v1/online-alerts/favicon", headers=admin, files={"file": ("x.txt", b"not an image", "text/plain")}
    )
    assert bad.status_code == 400, bad.text


async def test_tv_board_starts_from_the_website_colours(client, db_session, monkeypatch):
    ac, admin, _dish = await _ready(client, db_session, monkeypatch)
    menu = (await ac.get("/api/v1/restaurant/menu", headers=admin)).json()["data"]
    token = menu["settings"]["public_token"]
    await ac.patch("/api/v1/restaurant/menu/settings", headers=admin, json={"is_published": True})
    await ac.patch(
        "/api/v1/restaurant/menu/site-design",
        headers=admin,
        json={"primary": "#9A3412", "accent": "#F97316", "background": "#FFF7ED"},
    )
    theme = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["theme"]
    assert (theme["primary"], theme["accent"], theme["background"]) == ("#9A3412", "#F97316", "#FFF7ED")
    # The website design chooses the colours; an old menu colour does not override it.
    await ac.patch("/api/v1/restaurant/menu/settings", headers=admin, json={"primary_color": "#112233"})
    theme = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["theme"]
    assert theme["primary"] == "#9A3412" and theme["background"] == "#FFF7ED"
