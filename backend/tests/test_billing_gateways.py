"""Paystack and Flutterwave stay beside the sandbox gateway.

A browser return and an unsigned webhook never mark an invoice paid.
"""

from __future__ import annotations

import hashlib
import hmac
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
                "tenant_id": seed["t1"].id,
                "meta": {"tenant_id": seed["t1"].id},
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


async def test_named_gateway_uses_a_public_address_and_a_signed_webhook(client, monkeypatch):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    from app.billing_gateway import CheckoutResult, CustomGateway

    calls = {"post": 0}

    def _post(*_args, **_kwargs):
        calls["post"] += 1
        raise AssertionError("connection test must not create a charge")

    monkeypatch.setattr("app.billing_gateway.httpx.post", _post)
    monkeypatch.setattr(CustomGateway, "test_connection", lambda self: (True, "gateway_ok"))

    def _checkout(self, **kwargs):
        return CheckoutResult(True, "https://payments.example.com/pay", kwargs["reference"], "hosted_checkout")

    monkeypatch.setattr(CustomGateway, "checkout", _checkout)
    private = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={
            "provider": "hubtel",
            "mode": "sandbox",
            "secret": "hubtel_test_key",
            "webhook_secret": "hubtel_hook_secret",
            "api_base_url": "https://127.0.0.1/charge",
        },
        headers=owner,
    )
    assert private.status_code == 422, private.text
    garbage = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "not a name", "mode": "sandbox", "secret": "hubtel_test_key"},
        headers=owner,
    )
    assert garbage.status_code == 422, garbage.text
    saved = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={
            "provider": "hubtel",
            "mode": "sandbox",
            "secret": "hubtel_test_key",
            "webhook_secret": "hubtel_hook_secret",
            "api_base_url": "https://payments.example.com",
        },
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["webhook_url"].endswith("/api/v1/billing/webhooks/hubtel")
    assert "hubtel_test_key" not in saved.text
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    assert tested.json()["data"]["last_test_ok"] is True
    assert calls["post"] == 0
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
    assert checkout.json()["data"]["provider"] == "hubtel"
    reference = checkout.json()["data"]["reference"]

    def _post_event(event: dict, signature: str | None):
        raw = json.dumps(event, separators=(",", ":")).encode()
        outgoing = {"content-type": "application/json"}
        if signature is not None:
            outgoing["x-ribdigi-billing-signature"] = signature
        return ac.post("/api/v1/billing/webhooks/hubtel", content=raw, headers=outgoing)

    def _sign(event: dict) -> str:
        raw = json.dumps(event, separators=(",", ":")).encode()
        return hmac.new(b"hubtel_hook_secret", raw, hashlib.sha256).hexdigest()

    unsigned = await _post_event(
        {
            "id": "evt-open",
            "event": "charge.success",
            "data": {
                "reference": reference,
                "amount": 49900,
                "currency": "GHS",
                "status": "success",
                "authorization": {"authorization_code": "tok_ok", "reusable": True},
            },
        },
        None,
    )
    assert unsigned.status_code == 401, unsigned.text
    mismatch_event = {
        "id": "evt-mismatch",
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 1250,
            "currency": "GHS",
            "status": "success",
            "authorization": {"authorization_code": "tok_ok", "reusable": True},
        },
    }
    mismatch = await _post_event(mismatch_event, _sign(mismatch_event))
    assert mismatch.status_code == 200, mismatch.text
    assert mismatch.json()["data"]["outcome"] == "mismatch"
    account = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert account["authorization_present"] is False
    confirmed_event = {
        "id": "evt-ok",
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 49900,
            "currency": "GHS",
            "status": "success",
            "tenant_id": seed["t1"].id,
            "authorization": {"authorization_code": "tok_ok", "reusable": True},
        },
    }
    confirmed = await _post_event(confirmed_event, _sign(confirmed_event))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["outcome"] == "authorization_saved"
    assert "tok_ok" not in confirmed.text
    saved_account = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert saved_account["authorization_present"] is True
    assert saved_account["provider"]["provider"] == "hubtel"
    assert saved_account["provider"]["live_charges"] is False
    invoices = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert all(row["status"] != "paid" for row in invoices)

