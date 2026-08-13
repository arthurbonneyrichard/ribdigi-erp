"""Stage 167 T1 — offline catalog TTL / refresh policy."""

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
async def test_sync_pull_catalog_recommended_ttl_t1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "TTL device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    pulled = await ac.post(
        "/api/v1/sync/pull",
        headers=headers,
        json={"device_id": device_id, "include_catalog": True},
    )
    assert pulled.status_code == 200, pulled.text
    ops = pulled.json()["data"]["ops"]
    catalog = next(o for o in ops if o["op_type"] == "catalog_products")
    payload = catalog["payload"]
    assert payload.get("stock_authoritative") is False
    assert int(payload.get("recommended_ttl_seconds") or 0) == 4 * 60 * 60


def test_offline_catalog_ttl_module_and_pos_ui_t1():
    catalog = (ROOT / "frontend/lib/offlineCatalog.ts").read_text(encoding="utf-8")
    assert "DEFAULT_CATALOG_TTL_MS" in catalog
    assert "isOfflineCatalogExpired" in catalog
    assert "getOfflineCatalogFreshness" in catalog
    assert "expires_at" in catalog
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "TTL expired" in pos or "catalogExpired" in pos
    assert "getOfflineCatalogFreshness" in pos
    engine = (ROOT / "backend/app/sync_engine.py").read_text(encoding="utf-8")
    assert "recommended_ttl_seconds" in engine
