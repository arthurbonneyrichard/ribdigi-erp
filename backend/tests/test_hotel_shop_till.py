"""Hotel shop till: hotel's own sales tables; walk-up and charge-to-room; the retail till refuses a hotel."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _hotel_admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


async def _item(ac, headers, name, price, stock=20):
    made = await ac.post(
        "/api/v1/products", headers=headers, json={"name": name, "selling_price": price, "cost_price": price / 2, "stock_qty": stock}
    )
    assert made.status_code == 200, made.text
    return made.json()["data"]


async def _checked_in_folio(ac, headers):
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms", headers=headers,
        json={"code": f"S{suffix}", "name": f"Room {suffix}", "room_type": "standard", "rate_amount": 200, "max_occupancy": 2},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post("/api/v1/hotel/guests", headers=headers, json={"full_name": f"Guest {suffix}"})
    assert guest.status_code == 200, guest.text
    start = date.today()
    booked = await ac.post(
        "/api/v1/hotel/reservations", headers=headers,
        json={
            "room_id": room.json()["data"]["id"], "guest_id": guest.json()["data"]["id"],
            "check_in_date": start.isoformat(), "check_out_date": (start + timedelta(days=1)).isoformat(), "adults": 1,
        },
    )
    assert booked.status_code == 200, booked.text
    checked = await ac.post(f"/api/v1/hotel/reservations/{booked.json()['data']['id']}/check-in", headers=headers, json={})
    assert checked.status_code == 200, checked.text
    return checked.json()["data"]["folio_id"]


async def test_hotel_cannot_use_the_retail_till(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    # The hotel's own admin (platform roles skip industry gates by design).
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert opened.status_code == 403, opened.text


async def test_hotel_shop_walk_up_sale_needs_the_front_desk_shift(client, seeded, db_session):
    ac, seed = client
    admin = await _hotel_admin(ac, seed, db_session)
    water = await _item(ac, admin, "Water", 5)
    body = {"payment_method": "cash", "lines": [{"product_id": water["id"], "quantity": 2}]}
    refused = await ac.post("/api/v1/hotel/shop/sales", headers=admin, json=body)
    assert refused.status_code == 409, refused.text

    shift = await ac.post("/api/v1/hotel/cashier/shift/open", headers=admin, json={"opening_float": 50})
    assert shift.status_code == 200, shift.text
    sold = await ac.post("/api/v1/hotel/shop/sales", headers=admin, json=body)
    assert sold.status_code == 200, sold.text
    sale = sold.json()["data"]
    assert sale["sale_number"].startswith("HS-") and sale["total"] >= 10 and sale["shift_id"]

    stock = await ac.get(f"/api/v1/products/{water['id']}", headers=admin)
    assert float(stock.json()["data"]["stock_qty"]) == 18
    takings = (await ac.get("/api/v1/hotel/shop/takings", headers=admin)).json()["data"]
    assert takings["by_method"]["cash"] == sale["total"] and takings["sale_count"] == 1

    refunded = await ac.post(f"/api/v1/hotel/shop/sales/{sale['id']}/refund", headers=admin)
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["data"]["status"] == "refunded"
    stock = await ac.get(f"/api/v1/products/{water['id']}", headers=admin)
    assert float(stock.json()["data"]["stock_qty"]) == 20


async def test_hotel_shop_charge_to_room_lands_on_the_folio(client, seeded, db_session):
    ac, seed = client
    admin = await _hotel_admin(ac, seed, db_session)
    snack = await _item(ac, admin, "Chocolate", 8)
    folio_id = await _checked_in_folio(ac, admin)
    rooms = (await ac.get("/api/v1/hotel/shop/rooms", headers=admin)).json()["data"]
    assert any(row["folio_id"] == folio_id for row in rooms)

    before = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)).json()["data"]["charges_total"]
    sold = await ac.post(
        "/api/v1/hotel/shop/sales", headers=admin,
        json={"payment_method": "room", "folio_id": folio_id, "lines": [{"product_id": snack["id"], "quantity": 3}]},
    )
    assert sold.status_code == 200, sold.text
    sale = sold.json()["data"]
    assert sale["payment_method"] == "room" and sale["shift_id"] is None
    after = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)).json()["data"]["charges_total"]
    assert round(after - before, 2) == sale["total"]

    refunded = await ac.post(f"/api/v1/hotel/shop/sales/{sale['id']}/refund", headers=admin)
    assert refunded.status_code == 200, refunded.text
    back = (await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)).json()["data"]["charges_total"]
    assert back == before


async def test_retail_cannot_use_the_hotel_shop(client, seeded, db_session):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/hotel/shop/items", headers=admin)
    assert denied.status_code == 403, denied.text


def test_hotel_shop_has_its_own_screen_and_nav():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    nav = (root / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    page = (root / "frontend/app/(dashboard)/hotel/shop/page.tsx").read_text(encoding="utf-8")
    shift = (root / "frontend/lib/cashierShift.ts").read_text(encoding="utf-8")
    assert "['Shop till', '/hotel/shop', 'hotel']" in nav
    assert "'/hotel/shop/sales'" in page and "/pos/" not in page and "tpos" not in page
    assert "'/hotel/cashier/shift/close'" in shift
