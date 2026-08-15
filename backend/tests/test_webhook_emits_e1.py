"""Webhook fan-out for domain events beyond sale.created / webhook.test."""

from __future__ import annotations

import httpx
import pyotp
import pytest

from app import webhooks as webhooks_svc
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_customer_created_and_sale_paid_webhooks(client, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "body": request.content,
                "event": __import__("json").loads(request.content.decode()).get("event"),
            }
        )
        return httpx.Response(200, json={"ok": True})

    original = webhooks_svc._deliver_http

    async def _mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _mock)

    hook = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://hooks.example.com/emit",
            "events": ["customer.created", "sale.paid", "sale.created"],
        },
    )
    assert hook.status_code == 200, hook.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Webhook Customer", "code": "WH-CUST-1"},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]
    assert any(c["event"] == "customer.created" for c in captured)

    # Post invoice then pay to emit sale.created + sale.paid
    product = seed["p1"]
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10, "tax_rate": 0}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    pay = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "sales_invoice_id": invoice_id,
            "amount": 10,
            "payment_method": "cash",
        },
    )
    assert pay.status_code == 200, pay.text
    events = [c["event"] for c in captured]
    assert "sale.created" in events
    assert "sale.paid" in events


@pytest.mark.asyncio
async def test_purchase_order_created_webhook(client, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append(__import__("json").loads(request.content.decode()).get("event"))
        return httpx.Response(200, json={"ok": True})

    original = webhooks_svc._deliver_http

    async def _mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _mock)

    await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={"url": "https://hooks.example.com/po", "events": ["purchase.order.created"]},
    )

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Webhook Supplier", "code": "WH-SUP-1"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    product = seed["p1"]
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product.id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert po.status_code == 200, po.text
    assert "purchase.order.created" in events


@pytest.mark.asyncio
async def test_stock_in_webhook_skips_grn(client, db_session, monkeypatch):
    """Manual stock-in emits stock.in; GRN emits purchase.grn.received only (no double fan-out)."""
    from app import models as m

    ac, seed = client
    headers = await _admin(ac, seed)
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append(__import__("json").loads(request.content.decode()).get("event"))
        return httpx.Response(200, json={"ok": True})

    original = webhooks_svc._deliver_http

    async def _mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _mock)

    await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://hooks.example.com/stock",
            "events": ["stock.in", "purchase.grn.received"],
        },
    )

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": seed["p1"].id,
            "quantity": 3,
            "notes": "webhook stock.in proof",
        },
    )
    assert stock.status_code == 200, stock.text
    assert "stock.in" in events
    assert events.count("stock.in") == 1

    events.clear()
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "StockIn Skip GRN Vendor", "code": "WH-GRN-SKIP-1"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]
    po_row = await db_session.get(m.PurchaseOrder, po_id)
    po_row.status = "sent"
    await db_session.commit()

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 2,
                    "accepted_qty": 2,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    assert "purchase.grn.received" in events
    assert "stock.in" not in events


async def _open_pos_session(ac, headers):
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=headers,
                json={"actual_cash": 0},
            )
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()["data"].get("session_id") or opened.json()["data"]["id"]


@pytest.mark.asyncio
async def test_pos_sale_webhooks_cash_and_credit(client, db_session, monkeypatch):
    """Cash POS → sale.created + sale.paid; credit tender → sale.created only."""
    ac, seed = client
    headers = await _admin(ac, seed)
    events: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content.decode())
        events.append({"event": body.get("event"), "data": body.get("data") or {}})
        return httpx.Response(200, json={"ok": True})

    original = webhooks_svc._deliver_http

    async def _mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _mock)

    await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://hooks.example.com/pos",
            "events": ["sale.created", "sale.paid"],
        },
    )

    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    await db_session.commit()
    session_id = await _open_pos_session(ac, headers)

    cash = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 12}],
        },
    )
    assert cash.status_code == 200, cash.text
    names = [e["event"] for e in events]
    assert "sale.created" in names
    assert "sale.paid" in names
    created = next(e for e in events if e["event"] == "sale.created")
    assert created["data"].get("source") == "pos"
    assert created["data"].get("sale_id") == cash.json()["data"]["id"]

    events.clear()
    credit = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "credit",
            "party_id": seed["party1"].id,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 15}],
        },
    )
    assert credit.status_code == 200, credit.text
    names = [e["event"] for e in events]
    assert "sale.created" in names
    assert "sale.paid" not in names
    assert all(e["data"].get("source") == "pos" for e in events if e["event"] == "sale.created")
