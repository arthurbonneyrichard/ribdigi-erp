"""Bank API connector sync into reconciliation statements."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin_headers(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac,
        email="super@alpha.example.com",
        tenant_slug="alpha",
        totp_code=code,
    )


def test_mock_provider_blocked_in_production(monkeypatch):
    """The dev-only 'mock' provider (fake feed) must be rejected in production."""
    from fastapi import HTTPException

    from app import bank_connectors as bc

    monkeypatch.setattr("app.bank_connectors.settings.APP_ENV", "production")
    with pytest.raises(HTTPException) as exc:
        bc._normalize_provider("mock")
    assert exc.value.status_code == 400
    # a real feed provider stays allowed in production
    assert bc._normalize_provider("http_json") == "http_json"

    monkeypatch.setattr("app.bank_connectors.settings.APP_ENV", "development")
    assert bc._normalize_provider("mock") == "mock"


@pytest.mark.asyncio
async def test_mock_bank_connection_sync_and_dedupe(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.BANK_FEED_SYNC_ENABLED", True)
    monkeypatch.setattr("app.bank_connectors.settings.BANK_FEED_SYNC_ENABLED", True)

    ac, seeded = client
    headers = await _admin_headers(ac, seeded)

    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()["data"]
    bank = next((a for a in accounts if a.get("code") == "1010"), accounts[0])

    created = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "mock",
            "display_name": "Test feed",
            "external_account_id": "seed-alpha-1",
            "auto_sync": True,
            "auto_match_after_sync": False,
        },
    )
    assert created.status_code == 200, created.text
    conn = created.json()["data"]
    assert conn["provider"] == "mock"
    assert conn["has_credentials"] is False

    sync1 = await ac.post(
        f"/api/v1/accounting/bank-connections/{conn['id']}/sync",
        headers=headers,
        json={},
    )
    assert sync1.status_code == 200, sync1.text
    body1 = sync1.json()["data"]
    assert body1["imported"] >= 2
    assert body1["statement_id"]
    assert body1["skipped_duplicates"] == 0

    sync2 = await ac.post(
        f"/api/v1/accounting/bank-connections/{conn['id']}/sync",
        headers=headers,
        json={},
    )
    assert sync2.status_code == 200, sync2.text
    body2 = sync2.json()["data"]
    assert body2["imported"] == 0
    assert body2["skipped_duplicates"] >= 2

    listed = await ac.get("/api/v1/accounting/bank-connections", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1
    assert listed.json()["data"][0]["last_sync_status"] == "ok"

    settings = await ac.get("/api/v1/settings/bank-feed", headers=headers)
    assert settings.status_code == 200
    assert "mock" in settings.json()["data"]["providers"]

    deleted = await ac.delete(
        f"/api/v1/accounting/bank-connections/{conn['id']}", headers=headers
    )
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_http_json_provider_sync(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.BANK_FEED_SYNC_ENABLED", True)
    monkeypatch.setattr("app.bank_connectors.settings.BANK_FEED_SYNC_ENABLED", True)

    ac, seeded = client
    headers = await _admin_headers(ac, seeded)
    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()["data"]
    bank = next((a for a in accounts if a.get("code") == "1010"), accounts[0])

    created = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "http_json",
            "display_name": "HTTP feed",
            "feed_url": "https://bank.example/feed",
            "access_token": "secret-token",
            "auto_match_after_sync": False,
        },
    )
    assert created.status_code == 200, created.text
    conn_id = created.json()["data"]["id"]
    assert created.json()["data"]["has_credentials"] is True

    payload = {
        "opening_balance": 1000,
        "closing_balance": 1150,
        "transactions": [
            {
                "id": "txn-1",
                "date": "2026-08-01",
                "amount": 200,
                "description": "Customer transfer",
            },
            {
                "id": "txn-2",
                "date": "2026-08-02",
                "debit": 50,
                "credit": 0,
                "description": "Bank fee",
            },
        ],
    }

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None, params=None):
            assert url == "https://bank.example/feed"
            assert headers.get("Authorization") == "Bearer secret-token"
            return mock_resp

    with patch("httpx.AsyncClient", FakeClient):
        sync = await ac.post(
            f"/api/v1/accounting/bank-connections/{conn_id}/sync",
            headers=headers,
            json={},
        )
    assert sync.status_code == 200, sync.text
    data = sync.json()["data"]
    assert data["imported"] == 2
    assert data["provider"] == "http_json"
    assert data["statement_id"]

    detail = await ac.get(
        f"/api/v1/accounting/bank-statements/{data['statement_id']}", headers=headers
    )
    assert detail.status_code == 200
    lines = detail.json()["data"]["lines"]
    assert len(lines) == 2
    amounts = sorted(float(ln["amount"]) for ln in lines)
    assert amounts == [-50.0, 200.0]


@pytest.mark.asyncio
async def test_http_json_requires_feed_url(client):
    ac, seeded = client
    headers = await _admin_headers(ac, seeded)
    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()["data"]
    bank = accounts[0]
    r = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={"account_id": bank["id"], "provider": "http_json"},
    )
    assert r.status_code == 400
