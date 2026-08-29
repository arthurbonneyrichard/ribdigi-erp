"""Stage 6 W1: webhooks + HMAC-SHA256 delivery."""

from __future__ import annotations

import json

import httpx
import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import webhooks as webhooks_svc
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_hmac_sign_and_verify():
    body = b'{"event":"webhook.test","data":{}}'
    header, ts = webhooks_svc.sign_payload(secret="whsec_testsecret123456", body=body)
    assert header.startswith(f"t={ts},v1=")
    assert webhooks_svc.verify_signature(
        secret="whsec_testsecret123456", body=body, header=header
    )
    assert not webhooks_svc.verify_signature(
        secret="whsec_wrong", body=body, header=header
    )


def test_hmac_golden_fixture_matches_api_docs():
    """Stable vectors published in docs/API_DOCUMENTATION.md §17.4."""
    secret = "whsec_demo_secret_123456"
    body = (
        b'{"event":"webhook.test","timestamp":"2026-08-15T07:00:00Z",'
        b'"tenant_id":"demo","data":{"message":"ping"}}'
    )
    ts = 1723705200
    header, _ = webhooks_svc.sign_payload(secret=secret, body=body, timestamp=ts)
    assert (
        header
        == "t=1723705200,v1=8ba12e1df3b867331f2ccf13f760ace4afd370df9d542012046eb4aba49bb2e2"
    )
    assert webhooks_svc.verify_signature(
        secret=secret, body=body, header=header, tolerance_seconds=10**9
    )
    assert not webhooks_svc.verify_signature(
        secret=secret, body=body + b" ", header=header, tolerance_seconds=10**9
    )
    # skew rejection when "now" is far from fixture timestamp
    assert not webhooks_svc.verify_signature(
        secret=secret, body=body, header=header, tolerance_seconds=60
    )


@pytest.mark.asyncio
async def test_webhook_crud_and_signed_delivery(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        captured["signature"] = request.headers.get(webhooks_svc.SIGNATURE_HEADER)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    original_deliver = webhooks_svc._deliver_http

    async def _deliver_with_mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original_deliver(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _deliver_with_mock)

    created = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://hooks.example.com/ribdigi",
            "events": ["sale.created", "webhook.test"],
            "description": "Staging receiver",
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["secret"].startswith("whsec_")
    secret = data["secret"]
    webhook_id = data["id"]

    listed = await ac.get("/api/v1/webhooks", headers=headers)
    assert listed.status_code == 200
    assert any(r["id"] == webhook_id for r in listed.json()["data"])
    assert all("secret" not in r for r in listed.json()["data"])

    ping = await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    assert ping.status_code == 200, ping.text
    assert ping.json()["data"]["status"] == "delivered"
    assert captured.get("signature")
    assert webhooks_svc.verify_signature(
        secret=secret, body=captured["body"], header=captured["signature"]
    )
    payload = json.loads(captured["body"].decode("utf-8"))
    assert payload["event"] == "webhook.test"
    assert payload["tenant_id"] == seed["t1"].id

    # Fan-out sale.created
    deliveries = await webhooks_svc.emit_event(
        db_session,
        tenant_id=seed["t1"].id,
        event="sale.created",
        data={"invoice_id": "inv-demo", "amount": 12.5},
        transport=transport,
    )
    # emit uses deliver_to_endpoint which calls _deliver_http (mocked)
    await db_session.commit()
    assert len(deliveries) == 1
    assert deliveries[0].status == "delivered"

    row = (
        await db_session.execute(
            select(m.WebhookDelivery).where(
                m.WebhookDelivery.tenant_id == seed["t1"].id,
                m.WebhookDelivery.event == "sale.created",
            )
        )
    ).scalar_one()
    assert row.status == "delivered"

    deleted = await ac.delete(f"/api/v1/webhooks/{webhook_id}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_webhook_rejects_http_non_localhost(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    bad = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={"url": "http://evil.example.com/hook", "events": ["sale.created"]},
    )
    # WebhookUrlValue → 422 (was late service validate_url **400**)
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_webhook_unknown_event_rejected(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    bad = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={"url": "https://hooks.example.com/x", "events": ["not.real"]},
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_webhooks_list_is_active_filter(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://hooks.example.com/filter-demo",
            "events": ["webhook.test"],
            "description": "Filter Demo Webhook",
        },
    )
    assert created.status_code == 200, created.text
    wid = created.json()["data"]["id"]

    await ac.patch(
        f"/api/v1/webhooks/{wid}",
        headers=headers,
        json={"is_active": False},
    )

    all_rows = await ac.get("/api/v1/webhooks", headers=headers)
    assert wid in {r["id"] for r in all_rows.json()["data"]}

    active_only = await ac.get("/api/v1/webhooks?is_active=true", headers=headers)
    assert wid not in {r["id"] for r in active_only.json()["data"]}

    inactive_only = await ac.get("/api/v1/webhooks?is_active=false", headers=headers)
    assert wid in {r["id"] for r in inactive_only.json()["data"]}
    assert all(r["is_active"] is False for r in inactive_only.json()["data"])


def test_webhook_status_filter_ui_wired():
    from pathlib import Path

    integrations = (
        Path(__file__).resolve().parents[2] / "frontend/app/integrations/page.tsx"
    ).read_text(encoding="utf-8")
    assert "webhookManageFilter" in integrations
    assert 'aria-label="Webhook status filter"' in integrations
    assert "managedHooks" in integrations
    assert "[inactive]" in integrations
    assert "toggleActive" in integrations
