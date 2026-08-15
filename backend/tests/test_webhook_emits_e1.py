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
