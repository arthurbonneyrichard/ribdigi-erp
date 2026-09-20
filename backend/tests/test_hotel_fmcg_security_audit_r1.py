"""Hotel + FMCG security, concurrency, isolation, and E2E workflow audits."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _beta_hotel_admin(ac, seed, db_session):
    """Ensure beta has a company_admin with hotel/fmcg module access."""
    from sqlalchemy import select

    row = (
        await db_session.execute(select(m.User).where(m.User.email == "admin@beta.example.com"))
    ).scalar_one_or_none()
    if not row:
        row = m.User(
            tenant_id=seed["t2"].id,
            email="admin@beta.example.com",
            full_name="Beta Admin",
            password_hash=hash_password("SecurePass123!"),
            role="company_admin",
            email_verified=True,
            permissions=permissions_for_role("company_admin"),
            totp_enabled=False,
        )
        db_session.add(row)
        await db_session.commit()
    return await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")


@pytest.mark.asyncio
async def test_hotel_e2e_reservation_folio_invoice_checkout(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"E{suffix}", "name": f"E2E {suffix}", "rate_amount": 200, "room_type": "deluxe"},
    )
    assert room.status_code == 200, room.text
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=admin,
        json={
            "full_name": f"E2E Guest {suffix}",
            "email": f"e2e-{suffix}@example.com",
            "phone": "+233201234567",
        },
    )
    assert guest.status_code == 200, guest.text
    check_in = date.today()
    check_out = check_in + timedelta(days=2)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 2,
            "deposit_amount": 50,
            "deposit_method": "cash",
        },
    )
    assert booked.status_code == 200, booked.text
    res_id = booked.json()["data"]["id"]

    # Availability must exclude this room for overlapping dates
    avail = await ac.get(
        f"/api/v1/hotel/availability?check_in_date={check_in.isoformat()}&check_out_date={check_out.isoformat()}",
        headers=admin,
    )
    assert avail.status_code == 200
    assert all(r["id"] != room.json()["data"]["id"] for r in avail.json()["data"])

    cin = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-in", headers=admin, json={})
    assert cin.status_code == 200, cin.text
    folio_id = cin.json()["data"]["folio_id"]
    folio = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert folio.status_code == 200
    bal = folio.json()["data"]["balance"]
    if bal > 0:
        pay = await ac.post(
            f"/api/v1/hotel/folios/{folio_id}/payments",
            headers=admin,
            json={"method": "momo", "amount": bal, "reference": f"PAY-{suffix}"},
        )
        assert pay.status_code == 200, pay.text

    cout = await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-out", headers=admin, json={})
    assert cout.status_code == 200, cout.text
    folio2 = await ac.get(f"/api/v1/hotel/folios/{folio_id}", headers=admin)
    assert folio2.json()["data"]["status"] == "closed"
    inv_id = folio2.json()["data"].get("sales_invoice_id")
    assert inv_id, "checkout must create a sales invoice from folio"
    inv = await ac.get(f"/api/v1/sales/invoices/{inv_id}", headers=admin)
    assert inv.status_code == 200, inv.text
    assert float(inv.json()["data"]["total_amount"]) > 0

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    matched = next(r for r in rooms.json()["data"] if r["id"] == room.json()["data"]["id"])
    assert matched["status"] == "dirty"
    assert matched["housekeeping_status"] == "dirty"

    reports = await ac.get("/api/v1/hotel/reports", headers=admin)
    assert reports.status_code == 200
    assert "occupancy_rate" in reports.json()["data"]


@pytest.mark.asyncio
async def test_hotel_concurrent_double_booking_blocked(client, seeded):
    """Two overlapping bookings for the same room — only one may succeed."""
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"C{suffix}", "name": f"Concurrent {suffix}", "rate_amount": 90},
    )
    assert room.status_code == 200
    g1 = await ac.post(
        "/api/v1/hotel/guests", headers=admin, json={"full_name": f"A {suffix}"}
    )
    g2 = await ac.post(
        "/api/v1/hotel/guests", headers=admin, json={"full_name": f"B {suffix}"}
    )
    assert g1.status_code == 200 and g2.status_code == 200
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=3)
    room_id = room.json()["data"]["id"]
    payload_a = {
        "room_id": room_id,
        "guest_id": g1.json()["data"]["id"],
        "check_in_date": check_in.isoformat(),
        "check_out_date": check_out.isoformat(),
    }
    payload_b = {
        "room_id": room_id,
        "guest_id": g2.json()["data"]["id"],
        "check_in_date": (check_in + timedelta(days=1)).isoformat(),
        "check_out_date": (check_out + timedelta(days=1)).isoformat(),
    }

    async def book(payload):
        return await ac.post("/api/v1/hotel/reservations", headers=admin, json=payload)

    r1, r2 = await asyncio.gather(book(payload_a), book(payload_b))
    codes = sorted([r1.status_code, r2.status_code])
    # One success, one conflict (or both conflict if both lose race after recheck — still no double book)
    assert 200 in codes
    assert codes.count(200) == 1
    assert 409 in codes

    listed = await ac.get("/api/v1/hotel/reservations", headers=admin)
    active = [
        r
        for r in listed.json()["data"]
        if r["room_id"] == room_id and r["status"] in {"booked", "checked_in"}
    ]
    assert len(active) == 1


@pytest.mark.asyncio
async def test_hotel_cross_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    alpha = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    beta = await _beta_hotel_admin(ac, seed, db_session)
    suffix = uuid4().hex[:6]

    room = await ac.post(
        "/api/v1/hotel/rooms",
        headers=alpha,
        json={"code": f"X{suffix}", "name": f"Secret {suffix}", "rate_amount": 50},
    )
    assert room.status_code == 200
    room_id = room.json()["data"]["id"]
    guest = await ac.post(
        "/api/v1/hotel/guests",
        headers=alpha,
        json={"full_name": f"Secret Guest {suffix}", "email": f"sec-{suffix}@example.com"},
    )
    assert guest.status_code == 200
    guest_id = guest.json()["data"]["id"]
    check_in = date.today() + timedelta(days=20)
    booked = await ac.post(
        "/api/v1/hotel/reservations",
        headers=alpha,
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
        },
    )
    assert booked.status_code == 200
    res_id = booked.json()["data"]["id"]

    # Beta must not see alpha rooms/guests/reservations
    beta_rooms = await ac.get("/api/v1/hotel/rooms", headers=beta)
    assert beta_rooms.status_code == 200
    assert all(r["id"] != room_id for r in beta_rooms.json()["data"])

    beta_guests = await ac.get("/api/v1/hotel/guests", headers=beta)
    assert beta_guests.status_code == 200
    assert all(g["id"] != guest_id for g in beta_guests.json()["data"])

    # Direct IDOR attempts
    assert (await ac.patch(f"/api/v1/hotel/rooms/{room_id}", headers=beta, json={"name": "Hijack"})).status_code == 404
    assert (await ac.get(f"/api/v1/hotel/reservations/{res_id}/confirmation", headers=beta)).status_code == 404
    assert (await ac.post(f"/api/v1/hotel/reservations/{res_id}/check-in", headers=beta, json={})).status_code == 404

    settings = await ac.get("/api/v1/hotel/settings", headers=beta)
    assert settings.status_code == 200
    # Beta settings row is separate (created on read)
    alpha_settings = await ac.get("/api/v1/hotel/settings", headers=alpha)
    assert alpha_settings.json()["data"]["id"] != settings.json()["data"]["id"]


@pytest.mark.asyncio
async def test_fmcg_cross_tenant_isolation_and_e2e(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    alpha = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    beta = await _beta_hotel_admin(ac, seed, db_session)
    suffix = uuid4().hex[:6]

    scheme = await ac.post(
        "/api/v1/fmcg/schemes",
        headers=alpha,
        json={"code": f"ISO{suffix}", "name": "Iso", "scheme_type": "percent", "value": 5},
    )
    assert scheme.status_code == 200
    scheme_id = scheme.json()["data"]["id"]

    route = await ac.post(
        "/api/v1/fmcg/routes",
        headers=alpha,
        json={"code": f"IR{suffix}", "name": f"Iso Route {suffix}"},
    )
    assert route.status_code == 200
    route_id = route.json()["data"]["id"]

    # Beta list must not include alpha schemes/routes
    beta_schemes = await ac.get("/api/v1/fmcg/schemes", headers=beta)
    assert beta_schemes.status_code == 200
    assert all(s["id"] != scheme_id for s in beta_schemes.json()["data"])
    beta_routes = await ac.get("/api/v1/fmcg/routes", headers=beta)
    assert beta_routes.status_code == 200
    assert all(r["id"] != route_id for r in beta_routes.json()["data"])

    # IDOR
    assert (
        await ac.patch(
            f"/api/v1/fmcg/schemes/{scheme_id}",
            headers=beta,
            json={"is_active": False},
        )
    ).status_code == 404
    assert (await ac.get(f"/api/v1/fmcg/routes/{route_id}/stops", headers=beta)).status_code == 404

    # FMCG distribution E2E on alpha: customer → assignment → stop → dispatch → delivery
    customer = await ac.post(
        "/api/v1/customers",
        headers=alpha,
        json={"name": f"Distro {suffix}", "profile_type": "registered"},
    )
    assert customer.status_code == 200
    customer_id = customer.json()["data"]["id"]
    assign = await ac.post(
        "/api/v1/fmcg/assignments",
        headers=alpha,
        json={"customer_id": customer_id, "route_id": route_id, "salesperson_name": "Rep"},
    )
    assert assign.status_code == 200
    stop = await ac.post(
        f"/api/v1/fmcg/routes/{route_id}/stops",
        headers=alpha,
        json={"customer_id": customer_id, "sequence": 1, "visit_day": "tue"},
    )
    assert stop.status_code == 200
    dispatch = await ac.post(
        "/api/v1/fmcg/dispatches",
        headers=alpha,
        json={"route_id": route_id},
    )
    assert dispatch.status_code == 200
    delivered = await ac.patch(
        f"/api/v1/fmcg/stops/{stop.json()['data']['id']}/delivery",
        headers=alpha,
        json={"delivery_status": "delivered"},
    )
    assert delivered.status_code == 200
    closed = await ac.post(
        f"/api/v1/fmcg/dispatches/{dispatch.json()['data']['id']}/close",
        headers=alpha,
        json={},
    )
    assert closed.status_code == 200

    # Core product isolation still holds for FMCG tenants
    products = await ac.get("/api/v1/products", headers=alpha)
    assert products.status_code == 200
    assert all(p.get("name") != "Beta Widget" for p in products.json()["data"])
