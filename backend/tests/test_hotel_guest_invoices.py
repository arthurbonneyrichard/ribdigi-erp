"""Hotel guest invoices: folio invoices at check-out, what is owed, payments, and the hotel menu."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from tests.conftest import auth_headers, set_tenant_industry

ROOT = Path(__file__).resolve().parents[2] / "frontend"


@pytest.mark.asyncio
async def test_checkout_balance_shows_and_is_paid(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:6]
    room = await ac.post("/api/v1/hotel/rooms", headers=admin, json={"code": f"I{suffix}", "name": f"Inv {suffix}", "rate_amount": 100})
    assert room.status_code == 200, room.text
    guest = await ac.post("/api/v1/hotel/guests", headers=admin, json={"full_name": f"Invoice Guest {suffix}", "company_name": "Acme Ltd"})
    stay = await ac.post(
        "/api/v1/hotel/reservations",
        headers=admin,
        json={
            "room_id": room.json()["data"]["id"],
            "guest_id": guest.json()["data"]["id"],
            "check_in_date": (date.today() + timedelta(days=8)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    rid = stay.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/hotel/reservations/{rid}/check-in", headers=admin, json={})).status_code == 200
    out = await ac.post(f"/api/v1/hotel/reservations/{rid}/check-out", headers=admin, json={"allow_balance": True})
    assert out.status_code == 200, out.text

    owed = (await ac.get("/api/v1/hotel/invoices", headers=admin)).json()["data"]
    row = next(i for i in owed["items"] if i["guest_name"] == f"Invoice Guest {suffix}")
    assert row["due"] > 0 and row["company_name"] == "Acme Ltd" and row["room"].lower() == f"i{suffix}"
    assert owed["owed_total"] >= row["due"]

    too_much = await ac.post(f"/api/v1/hotel/invoices/{row['id']}/payments", headers=admin, json={"amount": row["due"] + 50, "method": "cash"})
    assert too_much.status_code == 422, too_much.text
    paid = await ac.post(f"/api/v1/hotel/invoices/{row['id']}/payments", headers=admin, json={"amount": row["due"], "method": "momo", "reference": "MOMO123"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["due"] == 0

    after = (await ac.get("/api/v1/hotel/invoices", headers=admin)).json()["data"]
    assert all(i["id"] != row["id"] for i in after["items"])
    every = (await ac.get("/api/v1/hotel/invoices?show=all", headers=admin)).json()["data"]
    assert any(i["id"] == row["id"] for i in every["items"])
    printed = await ac.get(f"/api/v1/hotel/invoices/{row['id']}/print", headers=admin)
    assert printed.status_code == 200 and "html" in printed.headers["content-type"]


@pytest.mark.asyncio
async def test_guest_invoices_are_hotel_only(client, db_session):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    res = await ac.get("/api/v1/hotel/invoices", headers=admin)
    assert res.status_code in {403, 404}, res.text


def test_hotel_menu_uses_guest_invoices():
    nav = (ROOT / "lib/tenantNav.ts").read_text(encoding="utf-8")
    groups = nav.split("export const HOTEL_NAV_GROUPS", 1)[1].split("\n];", 1)[0]
    assert "['Guest invoices', '/hotel/invoices', 'hotel']" in groups
    for gone in ("'/sales'", "'/customers'", "/sales?tab=giftcards", "/sales?tab=coupons", "/credit?kind=receivable"):
        assert gone not in groups
    assert "return ind === 'retail' || ind === 'pharmacy';" in nav
    page = (ROOT / "app/(dashboard)/hotel/invoices/page.tsx").read_text(encoding="utf-8")
    assert "`/hotel/invoices/${row.id}/payments`" in page and "`/hotel/invoices/${row.id}/print`" in page


def test_shell_shows_industry_block_instead_of_page():
    shell = (ROOT / "components/Shell.tsx").read_text(encoding="utf-8")
    assert ") : industryPageBlock ? (" in shell
    assert 'className="card industry-page-block"' in shell
    nav = (ROOT / "lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "Hotel bills are under Guest billing → Guest invoices" in nav
