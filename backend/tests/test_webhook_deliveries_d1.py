"""Webhook delivery history list + manual retry (Integrations UI)."""

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
async def test_list_deliveries_and_manual_retry(client, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    monkeypatch.setattr(webhooks_svc.settings, "WEBHOOK_MAX_ATTEMPTS", 5)
    monkeypatch.setattr(webhooks_svc.settings, "WEBHOOK_RETRY_BASE_SECONDS", 60)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"ok": True})

    original = webhooks_svc._deliver_http

    async def _deliver_with_mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original(
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
        json={"url": "https://hooks.example.com/history", "events": ["webhook.test"]},
    )
    assert created.status_code == 200, created.text
    webhook_id = created.json()["data"]["id"]

    ping = await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    assert ping.status_code == 200, ping.text
    delivery_id = ping.json()["data"]["id"]
    assert ping.json()["data"]["status"] == "pending_retry"
    assert ping.json()["data"]["can_retry"] is True

    listed = await ac.get(f"/api/v1/webhooks/{webhook_id}/deliveries", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r["id"] == delivery_id for r in rows)
    assert rows[0]["can_retry"] is True

    retried = await ac.post(
        f"/api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}/retry",
        headers=headers,
        json={},
    )
    assert retried.status_code == 200, retried.text
    body = retried.json()["data"]
    assert body["status"] == "delivered"
    assert body["attempt_count"] == 2
    assert body["can_retry"] is False

    # delivered cannot be retried again
    again = await ac.post(
        f"/api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}/retry",
        headers=headers,
        json={},
    )
    assert again.status_code == 400
