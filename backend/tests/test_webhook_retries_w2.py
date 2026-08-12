"""Stage 7 W2: webhook delivery retries with exponential backoff."""

from __future__ import annotations

from datetime import datetime, timedelta

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


def test_retry_delay_exponential(monkeypatch):
    monkeypatch.setattr(webhooks_svc.settings, "WEBHOOK_RETRY_BASE_SECONDS", 60)
    assert webhooks_svc.retry_delay_seconds(1) == 60
    assert webhooks_svc.retry_delay_seconds(2) == 300
    assert webhooks_svc.retry_delay_seconds(3) == 1500
    assert webhooks_svc.retry_delay_seconds(4) == 3600  # capped


@pytest.mark.asyncio
async def test_failed_delivery_schedules_retry_then_delivers(client, db_session, monkeypatch):
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
        json={"url": "https://hooks.example.com/retry", "events": ["webhook.test"]},
    )
    assert created.status_code == 200, created.text
    webhook_id = created.json()["data"]["id"]

    ping = await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    assert ping.status_code == 200, ping.text
    data = ping.json()["data"]
    assert data["status"] == "pending_retry"
    assert data["attempt_count"] == 1
    assert data["next_retry_at"]

    row = (
        await db_session.execute(
            select(m.WebhookDelivery).where(m.WebhookDelivery.id == data["id"])
        )
    ).scalar_one()
    assert row.status == "pending_retry"
    assert row.next_retry_at is not None

    # Not due yet
    early = await webhooks_svc.process_due_retries(
        db_session, tenant_id=seed["t1"].id, now=datetime.utcnow()
    )
    assert early["retried"] == 0

    # Force due
    row.next_retry_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    outcome = await webhooks_svc.process_due_retries(
        db_session, tenant_id=seed["t1"].id, now=datetime.utcnow()
    )
    await db_session.commit()
    assert outcome["retried"] == 1
    assert outcome["delivered"] == 1
    assert calls["n"] == 2

    await db_session.refresh(row)
    assert row.status == "delivered"
    assert row.attempt_count == 2
    assert row.next_retry_at is None
    assert row.delivered_at is not None


@pytest.mark.asyncio
async def test_max_attempts_marks_failed(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    monkeypatch.setattr(webhooks_svc.settings, "WEBHOOK_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(webhooks_svc.settings, "WEBHOOK_RETRY_BASE_SECONDS", 1)

    def always_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    original = webhooks_svc._deliver_http

    async def _deliver_with_mock(*, url, body, signature_header, timeout=10.0, transport=None):
        return await original(
            url=url,
            body=body,
            signature_header=signature_header,
            timeout=timeout,
            transport=httpx.MockTransport(always_fail),
        )

    monkeypatch.setattr(webhooks_svc, "_deliver_http", _deliver_with_mock)

    created = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={"url": "https://hooks.example.com/fail", "events": ["webhook.test"]},
    )
    webhook_id = created.json()["data"]["id"]
    ping = await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    assert ping.json()["data"]["status"] == "pending_retry"
    delivery_id = ping.json()["data"]["id"]

    row = await db_session.get(m.WebhookDelivery, delivery_id)
    row.next_retry_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    outcome = await webhooks_svc.process_due_retries(
        db_session, tenant_id=seed["t1"].id, now=datetime.utcnow()
    )
    await db_session.commit()
    assert outcome["failed"] == 1
    await db_session.refresh(row)
    assert row.status == "failed"
    assert row.attempt_count == 2
    assert row.next_retry_at is None
