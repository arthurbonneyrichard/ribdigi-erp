"""Paystack and Flutterwave stay beside the sandbox gateway.

A browser return and an unsigned webhook never mark an invoice paid.
"""

from __future__ import annotations

import json

import pytest

from app.billing_gateway import FlutterwaveGateway
from app.config import settings
from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio

_FLW_SECRET = "FLWSECK_TEST-abcdefghijkl"
_FLW_HOOK = "flutterwave-hook-secret"


async def test_unknown_provider_and_flutterwave_credentials_are_rejected(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    unknown = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "stripe", "mode": "sandbox", "secret": _FLW_SECRET},
        headers=owner,
    )
    assert unknown.status_code == 422, unknown.text
    bad_key = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "flutterwave", "mode": "sandbox", "secret": "not_a_test_key"},
        headers=owner,
    )
    assert bad_key.status_code == 422, bad_key.text
    foreign = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={
            "provider": "flutterwave",
            "mode": "sandbox",
            "secret": _FLW_SECRET,
            "api_base_url": "http://127.0.0.1/charge",
        },
        headers=owner,
    )
    assert foreign.status_code == 422, foreign.text
    denied = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "flutterwave", "mode": "sandbox", "secret": _FLW_SECRET},
        headers=admin,
    )
    assert denied.status_code == 403, denied.text


async def test_flutterwave_connection_does_not_charge(client, monkeypatch):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    calls = {"post": 0}

    def _refuse_post(*_args, **_kwargs):
        calls["post"] += 1
        raise AssertionError("connection test must not create a charge")

    monkeypatch.setattr("app.billing_gateway.httpx.post", _refuse_post)
    monkeypatch.setattr(FlutterwaveGateway, "test_connection", lambda self: (True, "flutterwave_ok"))
    saved = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={
            "provider": "flutterwave",
            "mode": "sandbox",
            "secret": _FLW_SECRET,
            "webhook_secret": _FLW_HOOK,
        },
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    assert _FLW_SECRET not in saved.text
    assert saved.json()["data"]["provider"] == "flutterwave"
    assert saved.json()["data"]["enabled"] is False
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    assert tested.json()["data"]["last_test_ok"] is True
    assert tested.json()["data"]["last_test_message"] == "flutterwave_ok"
    assert calls["post"] == 0
    enabled = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["data"]["connected"] is True
    assert enabled.json()["data"]["webhook_url"].endswith("/api/v1/billing/webhooks/flutterwave")


async def test_flutterwave_enable_requires_webhook_secret(client, monkeypatch):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    monkeypatch.setattr(FlutterwaveGateway, "test_connection", lambda self: (True, "flutterwave_ok"))
    saved = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "flutterwave", "mode": "sandbox", "secret": _FLW_SECRET},
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    blocked = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert blocked.status_code == 422, blocked.text


async def test_flutterwave_webhook_saves_method_only_when_signed_and_amount_matches(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "FLUTTERWAVE_WEBHOOK_HASH", _FLW_HOOK)
    owner = await platform_owner_headers(ac, seed)
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    monkeypatch.setattr(FlutterwaveGateway, "test_connection", lambda self: (True, "flutterwave_ok"))
    from app.billing_gateway import MockGateway

    MockGateway._charged.clear()
    saved = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "mocksecret1"},
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    enabled = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month"},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=headers,
    )
    assert consent.status_code == 200, consent.text
    checkout = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "professional-month"},
        headers=headers,
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["data"]["paid"] is False
    reference = checkout.json()["data"]["reference"]

    def _post(event: dict, header: str | None):
        raw = json.dumps(event, separators=(",", ":")).encode()
        headers_out = {"content-type": "application/json"}
        if header is not None:
            headers_out["verif-hash"] = header
        return ac.post("/api/v1/billing/webhooks/flutterwave", content=raw, headers=headers_out)

    unsigned = await _post(
        {
            "event": "charge.completed",
            "data": {"tx_ref": reference, "amount": 499, "currency": "GHS", "status": "successful"},
        },
        None,
    )
    assert unsigned.status_code == 401, unsigned.text
    mismatch = await _post(
        {
            "event": "charge.completed",
            "data": {
                "id": 81,
                "tx_ref": reference,
                "amount": 12.5,
                "currency": "GHS",
                "status": "successful",
                "card": {"token": "tok_ok"},
            },
        },
        _FLW_HOOK,
    )
    assert mismatch.status_code == 200, mismatch.text
    assert mismatch.json()["data"]["outcome"] == "mismatch"
    account = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert account["authorization_present"] is False
    confirmed = await _post(
        {
            "event": "charge.completed",
            "data": {
                "id": 82,
                "tx_ref": reference,
                "flw_ref": "FLW-LOCAL-1",
                "amount": 499,
                "currency": "GHS",
                "status": "successful",
                "customer": {"id": 12},
                "card": {"token": "tok_ok"},
            },
        },
        _FLW_HOOK,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["outcome"] == "authorization_saved"
    assert "tok_ok" not in confirmed.text
    saved_account = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert saved_account["authorization_present"] is True
    invoices = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert all(row["status"] != "paid" for row in invoices)
