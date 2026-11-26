"""Receipt printing for saved payments: idempotent, honest status, never touches the money.

The "printer" here is the till agent talking to the API. No physical printer is involved.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import func, select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


async def _agent_printer(ac, headers, name="Front receipt", **extra):
    issued = await ac.post("/api/v1/printers/agents/pairing-codes", headers=headers, json={"label": f"{name} till"})
    assert issued.status_code == 200, issued.text
    code = issued.json()["data"]["pairing_code"]
    paired = await ac.post("/api/v1/printers/agents/pair", json={"pairing_code": code})
    assert paired.status_code == 200, paired.text
    agent = paired.json()["data"]
    created = await ac.post(
        "/api/v1/printers",
        headers=headers,
        json={
            "name": name,
            "connection_type": "print_agent",
            "agent_id": agent["id"],
            "purposes": ["customer_receipt"],
            **extra,
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["data"], {"X-Print-Agent-Token": agent["agent_token"]}


async def _sale(ac, headers, db_session, seed, **extra):
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 50
    await db_session.commit()
    opened = await ac.post("/api/v1/pos/sessions/open", headers=headers, json={"opening_cash": 100})
    data = opened.json().get("data") if opened.status_code == 200 else None
    if data is None:
        data = (await ac.get("/api/v1/pos/sessions/current", headers=headers)).json()["data"]
    res = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": data.get("session_id") or data["id"],
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 2}],
            **extra,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def _print(ac, headers, sale_id, **extra):
    return await ac.post(
        "/api/v1/printers/receipts",
        headers=headers,
        json={"source_type": "pos_sale", "source_id": sale_id, **extra},
    )


async def _count(db_session, model):
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_sale_prints_once_through_the_agent_with_cash_and_change(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    printer, agent = await _agent_printer(ac, admin, host="192.168.1.130", port=9100)
    assert printer["host"] == "192.168.1.130" and printer["device"] is None
    sale = await _sale(ac, admin, db_session, seed, cash_tendered=200)
    assert [j["status"] for j in sale["print_jobs"]] == ["queued"]
    sales_before = await _count(db_session, m.Transaction)
    payments_before = await _count(db_session, m.PosPayment)

    # A repeated callback or double tap finds the same job.
    for _ in range(2):
        res = await _print(ac, admin, sale["id"], mode="auto")
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert [j["id"] for j in data["jobs"]] == [sale["print_jobs"][0]["id"]]
        assert data["receipt"]["cash_tendered"] == 200
        assert data["receipt"]["change_due"] == pytest.approx(200 - float(sale["total"]))

    claimed = (await ac.get("/api/v1/printers/agent/jobs", headers=agent)).json()["data"]
    assert len(claimed) == 1
    assert claimed[0]["target"] == "tcp:192.168.1.130:9100"
    raw = base64.b64decode(claimed[0]["escpos_base64"])
    assert raw.startswith(b"\x1b\x40") and raw.endswith(b"\x1d\x56\x00")
    assert sale["reference"].encode() in raw
    assert b"Cash received" in raw and b"Change" in raw
    assert (await ac.get("/api/v1/printers/agent/jobs", headers=agent)).json()["data"] == []

    done = await ac.post(
        f"/api/v1/printers/agent/jobs/{claimed[0]['id']}/complete", headers=agent, json={"status": "printed"}
    )
    assert done.status_code == 200, done.text
    late = await ac.post(
        f"/api/v1/printers/agent/jobs/{claimed[0]['id']}/complete",
        headers=agent,
        json={"status": "failed", "detail": "late report"},
    )
    assert late.json()["data"]["status"] == "printed"
    status = await ac.get(f"/api/v1/printers/receipts?source_type=pos_sale&source_id={sale['id']}", headers=admin)
    assert [j["status"] for j in status.json()["data"]["jobs"]] == ["printed"]
    assert await _count(db_session, m.Transaction) == sales_before
    assert await _count(db_session, m.PosPayment) == payments_before


async def test_failed_print_keeps_the_sale_and_retries_then_reprints(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    _, agent = await _agent_printer(ac, admin, device="windows:Xprinter XP-80")
    sale = await _sale(ac, admin, db_session, seed)
    job = (await ac.get("/api/v1/printers/agent/jobs", headers=agent)).json()["data"][0]
    assert job["target"] == "windows:Xprinter XP-80"

    # While a copy is still on its way, "reprint" does not queue a second one.
    waiting = (await _print(ac, admin, sale["id"], mode="reprint")).json()["data"]["jobs"]
    assert [j["id"] for j in waiting] == [job["id"]]

    await ac.post(
        f"/api/v1/printers/agent/jobs/{job['id']}/complete",
        headers=agent,
        json={"status": "failed", "detail": "Printer is offline"},
    )
    shown = (await _print(ac, admin, sale["id"], mode="print")).json()["data"]["jobs"]
    assert shown[0]["status"] == "failed" and shown[0]["last_error"] == "Printer is offline"
    stored = await db_session.get(m.Transaction, sale["id"])
    assert stored.status == "completed"

    retried = (await _print(ac, admin, sale["id"], mode="retry")).json()["data"]["jobs"]
    assert [(j["id"], j["status"]) for j in retried] == [(job["id"], "queued")]
    again = (await ac.get("/api/v1/printers/agent/jobs", headers=agent)).json()["data"][0]
    await ac.post(f"/api/v1/printers/agent/jobs/{again['id']}/complete", headers=agent, json={"status": "printed"})

    sales_before = await _count(db_session, m.Transaction)
    copy = (await _print(ac, admin, sale["id"], mode="reprint")).json()["data"]["jobs"]
    assert copy[0]["id"] != job["id"] and copy[0]["reprint_of_job_id"] == job["id"]
    claimed = (await ac.get("/api/v1/printers/agent/jobs", headers=agent)).json()["data"][0]
    assert b"*** REPRINT ***" in base64.b64decode(claimed["escpos_base64"])
    assert await _count(db_session, m.Transaction) == sales_before


async def test_terminal_picks_its_printer_and_can_switch_auto_print_off(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    await _agent_printer(ac, admin, name="Till one")
    second, _ = await _agent_printer(ac, admin, name="Till two")
    saved = await ac.put(
        "/api/v1/printers/terminals/dev-two",
        headers=admin,
        json={"name": "Counter two", "receipt_printer_id": second["id"]},
    )
    assert saved.status_code == 200, saved.text
    sale = await _sale(ac, admin, db_session, seed, device_id="dev-two")
    assert [j["printer_id"] for j in sale["print_jobs"]] == [second["id"]]

    off = await ac.put("/api/v1/printers/terminals/dev-two", headers=admin, json={"auto_print": False})
    assert off.status_code == 200, off.text
    quiet = await _sale(ac, admin, db_session, seed, device_id="dev-two")
    assert quiet["print_jobs"] == []
    auto = (await _print(ac, admin, quiet["id"], mode="auto", terminal_id="dev-two")).json()["data"]
    assert auto["auto_print"] is False and auto["jobs"] == []
    asked = (await _print(ac, admin, quiet["id"], mode="print", terminal_id="dev-two")).json()["data"]
    assert len(asked["jobs"]) == 2

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.put("/api/v1/printers/terminals/dev-two", headers=cashier, json={"auto_print": True})
    assert denied.status_code == 403


async def test_no_printer_means_no_job_and_the_sale_stands(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    sale = await _sale(ac, admin, db_session, seed)
    res = (await _print(ac, admin, sale["id"])).json()["data"]
    assert res["jobs"] == [] and res["receipt"]["reference"] == sale["reference"]
    # No printer can print by itself, so the receipt is offered for a manual print.
    assert sale["reference"] in res["fallback"]["html"]
    again = (await _print(ac, admin, sale["id"], mode="reprint")).json()["data"]
    assert sale["reference"] in again["fallback"]["text"]
    # Once a printer is added, Retry prints the same saved sale.
    await _agent_printer(ac, admin, name="Added later")
    retried = (await _print(ac, admin, sale["id"], mode="retry")).json()["data"]
    assert [j["status"] for j in retried["jobs"]] == ["queued"]


async def test_unpaid_unknown_and_foreign_documents_never_print(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await _agent_printer(ac, admin)
    open_order = m.RestaurantOrder(
        tenant_id=seed["t1"].id, order_number="R-1", service_mode="takeaway", status="sent",
        payment_method="cash", subtotal=10, total_amount=10,
    )
    foreign = m.RestaurantOrder(
        tenant_id=seed["t2"].id, order_number="R-2", service_mode="takeaway", status="completed",
        payment_method="cash", subtotal=10, total_amount=10,
    )
    db_session.add_all([open_order, foreign])
    await db_session.commit()

    async def ask(source_id, source_type="restaurant_order"):
        return await ac.post(
            "/api/v1/printers/receipts",
            headers=admin,
            json={"source_type": source_type, "source_id": source_id},
        )

    unpaid = await ask(open_order.id)
    assert unpaid.status_code == 409, unpaid.text
    assert unpaid.json()["detail"]["code"] == "PAYMENT_NOT_CONFIRMED"
    assert (await ask(foreign.id)).status_code == 404
    assert (await ask("00000000-0000-0000-0000-000000000000")).status_code == 404
    assert (await ask(open_order.id, "anything_else")).status_code == 422
    assert await _count(db_session, m.PrintJob) == 0

    open_order.status = "completed"
    open_order.completed_at = datetime.utcnow()
    await db_session.commit()
    paid = await ask(open_order.id)
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["receipt"]["total"] == 10
    assert len(paid.json()["data"]["jobs"]) == 1


async def test_old_queued_jobs_expire_instead_of_printing_days_later(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    _, agent = await _agent_printer(ac, admin)
    sale = await _sale(ac, admin, db_session, seed)
    job = await db_session.get(m.PrintJob, sale["print_jobs"][0]["id"])
    job.updated_at = datetime.utcnow() - timedelta(hours=13)
    await db_session.commit()
    assert (await ac.get("/api/v1/printers/agent/jobs", headers=agent)).json()["data"] == []
    status = await ac.get(f"/api/v1/printers/receipts?source_type=pos_sale&source_id={sale['id']}", headers=admin)
    assert status.json()["data"]["jobs"][0]["status"] == "failed"


async def test_print_agents_have_their_own_rate_bucket():
    from app.middleware import PRINT_AGENT_PER_MINUTE, RateLimitMiddleware

    limiter = RateLimitMiddleware(app=None)
    assert limiter._limit_for_path("/api/v1/printers/agent/jobs") == PRINT_AGENT_PER_MINUTE
    assert limiter._limit_for_path("/api/v1/printers/agents/pair", "POST") != PRINT_AGENT_PER_MINUTE


async def test_till_device_names_are_checked(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    issued = await ac.post("/api/v1/printers/agents/pairing-codes", headers=admin, json={"label": "Bad till"})
    code = issued.json()["data"]["pairing_code"]
    agent_id = (await ac.post("/api/v1/printers/agents/pair", json={"pairing_code": code})).json()["data"]["id"]
    for bad in ("file:/etc/passwd", "windows:\\\\server\\share", "serial:/dev/mem", "windows:"):
        res = await ac.post(
            "/api/v1/printers",
            headers=admin,
            json={"name": "Bad", "connection_type": "print_agent", "agent_id": agent_id, "device": bad},
        )
        assert res.status_code == 400, (bad, res.text)
