"""Stage 126 W1 — paused webhooks honesty (?is_active=false)."""

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
async def test_webhooks_is_active_paused_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/hooks/stage126-paused",
            "events": ["webhook.test"],
            "description": "Stage126 Soon Paused",
        },
    )
    assert created.status_code == 200, created.text
    wid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/webhooks/{wid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["is_active"] is False

    paused = await ac.get("/api/v1/webhooks?is_active=false", headers=headers)
    assert paused.status_code == 200, paused.text
    rows = paused.json()["data"]
    assert any(r["id"] == wid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/webhooks?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == wid for r in active.json()["data"])

    resumed = await ac.patch(
        f"/api/v1/webhooks/{wid}",
        headers=headers,
        json={"is_active": True},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["is_active"] is True


def test_shell_and_security_paused_webhooks_w1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "webhook_active=false" in shell
    assert "Paused Webhooks" in shell
    assert "Active Webhooks" in shell
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 126" in page
    assert "webhookActiveFilter" in page
    assert "webhook_active" in page
