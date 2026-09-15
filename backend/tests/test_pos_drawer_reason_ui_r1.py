"""POS manual drawer open reason UI (BR-8.1) — no window.prompt."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_drawer_reason_ui_wired():
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "drawerReason" in pos
    assert "Drawer reason (required)" in pos
    assert 'aria-label="Cash drawer open reason"' in pos
    assert 'aria-label="Open cash drawer"' in pos
    assert "Reason for opening the cash drawer (required)" not in pos
    assert "/pos/sessions/${session.session_id}/drawer/open" in pos
    assert "Enter a specific drawer reason (min 3 characters)" in pos
    drawer_block_start = pos.find("Drawer reason (required)")
    drawer_block = pos[drawer_block_start : drawer_block_start + 1200]
    assert "window.prompt" not in drawer_block


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
