"""Stage 165 R1 — conflict resolve API + honesty (no silent re-apply)."""

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
async def test_sync_conflict_resolve_keep_server_r1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Resolve device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {"client_op_id": "resolve-op-1", "op_type": "ping", "payload": {"n": 1}}
            ],
        },
    )
    conflicted = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {"client_op_id": "resolve-op-1", "op_type": "ping", "payload": {"n": 2}}
            ],
        },
    )
    assert conflicted.status_code == 200, conflicted.text
    conflict_id = conflicted.json()["data"]["results"][0]["conflict"]["id"]

    resolved = await ac.post(
        f"/api/v1/sync/conflicts/{conflict_id}/resolve",
        headers=headers,
        json={"resolution": "keep_server"},
    )
    assert resolved.status_code == 200, resolved.text
    data = resolved.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolution"] == "keep_server"
    assert "re-applied" in (data.get("message") or "").lower() or "not re-applied" in (
        resolved.json().get("message") or data.get("message") or ""
    ).lower() or "not re-applied" in str(resolved.json()).lower()

    open_list = await ac.get("/api/v1/sync/conflicts?status=open", headers=headers)
    assert not any(r["id"] == conflict_id for r in open_list.json()["data"])


def test_settings_resolve_ui_r1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "/sync/conflicts/" in company
    assert "Keep server" in company or "keep_server" in company
    assert "resolve" in company.lower()
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "/sync/conflicts/{conflict_id}/resolve" in api
