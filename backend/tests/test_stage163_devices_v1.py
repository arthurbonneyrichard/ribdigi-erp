"""Stage 163 V1 — offline devices model/API/Settings UI."""

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


async def _cashier(ac, seed):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_offline_devices_register_list_revoke_v1(client):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Front counter tablet", "platform": "web"},
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["name"] == "Front counter tablet"
    assert data["device_code"].startswith("ofd_")
    assert data["status"] == "active"
    device_id = data["id"]

    listed = await ac.get("/api/v1/offline/devices?status=active", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(r["id"] == device_id for r in listed.json()["data"])

    got = await ac.get(f"/api/v1/offline/devices/{device_id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["device_code"] == data["device_code"]

    revoked = await ac.delete(f"/api/v1/offline/devices/{device_id}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["status"] == "revoked"
    assert revoked.json()["data"]["revoked_at"] is not None

    only_revoked = await ac.get("/api/v1/offline/devices?status=revoked", headers=headers)
    assert any(r["id"] == device_id for r in only_revoked.json()["data"])
    active_after = await ac.get("/api/v1/offline/devices?status=active", headers=headers)
    assert not any(r["id"] == device_id for r in active_after.json()["data"])


@pytest.mark.asyncio
async def test_offline_devices_rbac_and_tenant_isolation_v1(client):
    ac, seed = client
    cashier = await _cashier(ac, seed)
    denied = await ac.post(
        "/api/v1/offline/devices",
        headers=cashier,
        json={"name": "Should fail", "platform": "web"},
    )
    assert denied.status_code in {401, 403}, denied.text

    admin = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/offline/devices",
        headers=admin,
        json={"name": "Alpha only", "platform": "android"},
    )
    assert created.status_code == 200, created.text
    device_id = created.json()["data"]["id"]

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    # Beta cashier lacks admin; also ensure no cross-tenant leak for admin of alpha via beta tenant header.
    miss = await ac.get(f"/api/v1/offline/devices/{device_id}", headers=beta)
    assert miss.status_code in {401, 403, 404}, miss.text


def test_offline_device_model_and_migration_v1():
    models = (ROOT / "backend/app/models.py").read_text(encoding="utf-8")
    assert "class OfflineDevice" in models
    assert 'offline_devices' in models
    mig = (ROOT / "backend/alembic/versions/20260813_0091_offline_devices.py").read_text(
        encoding="utf-8"
    )
    assert "20260813_0091" in mig
    assert "offline_devices" in mig
    assert "20260812_0090" in mig


def test_settings_offline_sync_ui_and_shell_leaf_v1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="offline-sync"' in page
    assert "/offline/devices" in page
    assert "Stage 163" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/company#offline-sync" in shell
    assert "Offline sync" in shell
