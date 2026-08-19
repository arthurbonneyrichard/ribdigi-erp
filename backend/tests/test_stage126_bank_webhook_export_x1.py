"""Stage 126 X1 — bank connections / webhooks CSV export (no secrets)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_bank_connections_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()["data"]
    bank = next((a for a in accounts if a.get("code") == "1010"), accounts[0])

    created = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "mock",
            "display_name": "Export Conn 126",
            "external_account_id": "stage126-export-1",
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get(
        "/api/v1/accounting/bank-connections/export?active_only=false", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "provider" in header and "is_active" in header
    assert "credentials" not in header.lower() and "secret" not in header.lower()
    assert "Export Conn 126" in exported.text or "stage126-export-1" in exported.text


@pytest.mark.asyncio
async def test_webhooks_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/hooks/stage126-export",
            "events": ["webhook.test"],
            "description": "Export Webhook 126",
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/webhooks/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "url" in header and "is_active" in header
    assert "secret" not in header.lower()
    assert "stage126-export" in exported.text or "Export Webhook 126" in exported.text


def test_bank_webhook_export_ui_and_service_x1():
    acc = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 126" in acc
    assert "/accounting/bank-connections/export" in acc
    assert "Export bank connections CSV" in acc
    sec = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "/webhooks/export" in sec
    assert "Export webhooks CSV" in sec
    svc = (ROOT / "backend/app/bank_webhook_export.py").read_text(encoding="utf-8")
    assert "export_bank_connections_csv" in svc
    assert "export_webhooks_csv" in svc
