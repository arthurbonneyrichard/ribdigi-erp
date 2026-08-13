"""Integrations admin API paths used by /integrations UI (BR-18.1 / BR-18.6)."""

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
async def test_integrations_admin_key_and_webhook_flow(client, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)

    keys = await ac.get("/api/v1/api-keys", headers=headers)
    assert keys.status_code == 200

    created_key = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "UI integrator"},
    )
    assert created_key.status_code == 200, created_key.text
    key = created_key.json()["data"]
    assert key.get("api_key", "").startswith("rdk_")
    key_id = key["id"]

    usage = await ac.get(f"/api/v1/api-keys/{key_id}/usage", headers=headers)
    assert usage.status_code == 200

    hooks = await ac.get("/api/v1/webhooks", headers=headers)
    assert hooks.status_code == 200

    original_deliver = webhooks_svc._deliver_http

    async def _deliver_with_mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original_deliver(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(lambda _req: httpx.Response(200, json={"ok": True})),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _deliver_with_mock)

    created_hook = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/ribdigi-hook",
            "events": ["sale.created", "webhook.test"],
            "description": "UI test",
        },
    )
    assert created_hook.status_code == 200, created_hook.text
    hook = created_hook.json()["data"]
    assert hook.get("secret", "").startswith("whsec_")
    hook_id = hook["id"]

    tested = await ac.post(f"/api/v1/webhooks/{hook_id}/test", headers=headers, json={})
    assert tested.status_code == 200, tested.text
    assert tested.json()["data"]["status"] == "delivered"

    rotated = await ac.patch(
        f"/api/v1/webhooks/{hook_id}",
        headers=headers,
        json={"rotate_secret": True},
    )
    assert rotated.status_code == 200
    assert rotated.json()["data"].get("secret", "").startswith("whsec_")

    revoked = await ac.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert revoked.status_code == 200

    deleted = await ac.delete(f"/api/v1/webhooks/{hook_id}", headers=headers)
    assert deleted.status_code == 200
