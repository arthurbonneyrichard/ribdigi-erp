"""Restaurant orders print kitchen and bar tickets on the right printers when sent."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _printer(ac, headers, name: str, purpose: str) -> dict:
    res = await ac.post("/api/v1/printers", headers=headers, json={"name": name, "purposes": [purpose], "connection_type": "browser_dialog"})
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def _product(ac, headers, name: str, station: str) -> str:
    res = await ac.post("/api/v1/products", headers=headers, json={"name": name, "selling_price": 20, "stock_qty": 50, "prep_station": station})
    assert res.status_code == 200, res.text
    return res.json()["data"]["id"]


async def test_send_prints_each_station_once_then_added_dishes(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    kitchen = await _printer(ac, admin, "Kitchen printer", "kitchen")
    bar = await _printer(ac, admin, "Bar printer", "bar")
    rice = await _product(ac, admin, "Print jollof", "kitchen")
    juice = await _product(ac, admin, "Print sobolo", "bar")
    soup = await _product(ac, admin, "Print light soup", "kitchen")

    order = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "customer_name": "Ama", "lines": [{"product_id": rice, "quantity": "2"}, {"product_id": juice, "quantity": "1"}]},
    )
    assert order.status_code == 200, order.text
    oid = order.json()["data"]["id"]

    async def jobs():
        res = await ac.get(f"/api/v1/printers/jobs?source_id={oid}", headers=admin)
        assert res.status_code == 200, res.text
        return res.json()["data"]

    assert await jobs() == []
    assert (await ac.post(f"/api/v1/restaurant/orders/{oid}/send", headers=admin)).status_code == 200
    first = await jobs()
    assert {(j["printer_id"], j["purpose"]) for j in first} == {(kitchen["id"], "kitchen"), (bar["id"], "bar")}

    # Sending again prints nothing new.
    assert (await ac.post(f"/api/v1/restaurant/orders/{oid}/send", headers=admin)).status_code == 200
    assert len(await jobs()) == 2

    added = await ac.patch(f"/api/v1/restaurant/orders/{oid}", headers=admin, json={"lines": [{"product_id": soup, "quantity": "1"}]})
    assert added.status_code == 200, added.text
    after = await jobs()
    assert len(after) == 3
    extra = [j for j in after if j["id"] not in {x["id"] for x in first}]
    assert extra[0]["printer_id"] == kitchen["id"] and extra[0]["purpose"] == "kitchen"


async def test_no_printers_send_still_works(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, "Plain jollof", "kitchen")
    order = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "customer_name": "Kofi", "lines": [{"product_id": rice, "quantity": "1"}]},
    )
    sent = await ac.post(f"/api/v1/restaurant/orders/{order.json()['data']['id']}/send", headers=admin)
    assert sent.status_code == 200, sent.text


async def test_kitchen_screen_print_queue(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await _printer(ac, admin, "Kitchen tablet", "kitchen")
    rice = await _product(ac, admin, "Queue jollof", "kitchen")
    order = await ac.post(
        "/api/v1/restaurant/orders",
        headers=admin,
        json={"service_mode": "takeaway", "payment_method": "cash", "customer_name": "Esi", "lines": [{"product_id": rice, "quantity": "1"}]},
    )
    await ac.post(f"/api/v1/restaurant/orders/{order.json()['data']['id']}/send", headers=admin)
    queue = (await ac.get("/api/v1/restaurant/print-queue?station=kitchen", headers=admin)).json()["data"]
    assert len(queue) == 1 and "Queue jollof" in queue[0]["text"]
    assert (await ac.get("/api/v1/restaurant/print-queue?station=bar", headers=admin)).json()["data"] == []

    made = await ac.post(
        "/api/v1/users", headers=admin,
        json={"email": "k2@alpha.example.com", "full_name": "Kitchen Two", "password": "SecurePass123!", "role": "restaurant_kitchen"},
    )
    assert made.status_code == 200, made.text
    kitchen = await auth_headers(ac, email="k2@alpha.example.com", tenant_slug="alpha")
    done = await ac.post(f"/api/v1/restaurant/print-queue/{queue[0]['id']}/printed", headers=kitchen, json={"status": "printed"})
    assert done.status_code == 200, done.text
    assert (await ac.get("/api/v1/restaurant/print-queue?station=kitchen", headers=admin)).json()["data"] == []


async def test_admin_chooses_screen_printer_or_both(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rice = await _product(ac, admin, "Choice jollof", "kitchen")

    assert (await ac.get("/api/v1/restaurant/ticket-delivery", headers=admin)).json()["data"] == {"mode": "both", "printers": 0}
    # Printer only with no printer would send orders nowhere.
    refused = await ac.put("/api/v1/restaurant/ticket-delivery", headers=admin, json={"mode": "printer"})
    assert refused.status_code == 409
    assert (await ac.put("/api/v1/restaurant/ticket-delivery", headers=admin, json={"mode": "bogus"})).status_code == 422

    kitchen = await _printer(ac, admin, "Choice kitchen printer", "kitchen")

    async def send_and_count() -> int:
        order = await ac.post(
            "/api/v1/restaurant/orders",
            headers=admin,
            json={"service_mode": "takeaway", "payment_method": "cash", "customer_name": "Yaw", "lines": [{"product_id": rice, "quantity": "1"}]},
        )
        oid = order.json()["data"]["id"]
        assert (await ac.post(f"/api/v1/restaurant/orders/{oid}/send", headers=admin)).status_code == 200
        return len((await ac.get(f"/api/v1/printers/jobs?source_id={oid}", headers=admin)).json()["data"])

    # Screen only: the kitchen board still gets the order, nothing prints.
    assert (await ac.put("/api/v1/restaurant/ticket-delivery", headers=admin, json={"mode": "screen"})).status_code == 200
    assert await send_and_count() == 0
    assert len((await ac.get("/api/v1/restaurant/kitchen", headers=admin)).json()["data"]) >= 1

    for mode in ("printer", "both"):
        saved = await ac.put("/api/v1/restaurant/ticket-delivery", headers=admin, json={"mode": mode})
        assert saved.status_code == 200 and saved.json()["data"] == {"mode": mode, "printers": 1}, saved.text
        assert await send_and_count() == 1
    assert kitchen["id"]
