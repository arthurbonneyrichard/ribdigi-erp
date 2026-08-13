"""Stage 167 U1 — conflict re-apply UX polish (summary + Settings)."""

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
async def test_sync_conflict_summary_fields_u1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "UX device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [{"client_op_id": "ux-conflict-1", "op_type": "ping", "payload": {"n": 1}}],
        },
    )
    conflicted = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [{"client_op_id": "ux-conflict-1", "op_type": "ping", "payload": {"n": 2}}],
        },
    )
    assert conflicted.status_code == 200, conflicted.text
    conflict = conflicted.json()["data"]["results"][0]["conflict"]
    summary = conflict.get("summary") or {}
    assert summary.get("reason")
    assert "n" in (summary.get("client_payload_keys") or [])
    assert "never applied" in (summary.get("accept_client_policy") or "").lower()

    listed = await ac.get("/api/v1/sync/conflicts?status=open", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json()["data"] if r["id"] == conflict["id"])
    assert row.get("summary", {}).get("accept_client_policy")


def test_settings_conflict_summary_ui_u1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "summary" in company
    assert "accept_client_policy" in company or "client keys" in company
    assert "Accept client" in company
    engine = (ROOT / "backend/app/sync_engine.py").read_text(encoding="utf-8")
    assert '"summary"' in engine or "summary" in engine
    assert "client_payload_keys" in engine
