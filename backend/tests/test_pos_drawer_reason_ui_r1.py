"""POS manual drawer open reason UI (BR-8.1) — no window.prompt."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_drawer_reason_ui_wired():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    assert "drawerReason" in shell
    assert 'aria-label="Cash drawer open reason"' in shell
    assert 'aria-label="Open drawer"' in shell
    assert "Open drawer" in shell
    assert "window.prompt" not in shell
    assert "/pos/sessions/${sessionId}/drawer/open" in shell
    assert "setPosDrawerBridge" in pos
    topbar = shell[shell.find('className="topbar-left"') : shell.find('className="topbar-left"') + 500]
    assert "PosSellingStatus" in topbar
    assert "PosDrawerTopControls" in topbar


async def _cashier_headers(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_pos_drawer_open_with_reason_via_api(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "mock")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "mock")

    ac, _seed = client
    headers = await _cashier_headers(ac)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    bad = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "manual"},
    )
    assert bad.status_code == 422, bad.text

    ok = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "Change for walk-in — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["ok"] is True
    assert body["reason"] == "Change for walk-in — API hello-world"
