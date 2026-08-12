"""Stage 144 W1 — webhook deliveries list + CSV (payload excluded)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pyotp
import pytest

from app import webhooks as webhooks_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_webhook_deliveries_list_and_export(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

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
            "url": "https://example.test/hooks/stage144",
            "events": ["webhook.test"],
            "description": "Stage144",
        },
    )
    assert created.status_code == 200, created.text
    webhook_id = created.json()["data"]["id"]

    ping = await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    assert ping.status_code == 200, ping.text
    delivery_id = ping.json()["data"]["id"]

    listed = await ac.get("/api/v1/webhooks/deliveries", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r.get("id") == delivery_id for r in rows)
    for r in rows:
        assert "payload" not in r

    exported = await ac.get("/api/v1/webhooks/deliveries/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "webhook_id" in header and "event" in header and "status" in header
    assert delivery_id in text
    assert webhook_id in text
    assert "payload" not in header.lower()
    assert "secret" not in header.lower()
    assert "whsec_" not in text


def test_webhook_deliveries_export_ui_w1():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 144" in page
    assert "/webhooks/deliveries/export" in page
    assert "Export deliveries CSV" in page
