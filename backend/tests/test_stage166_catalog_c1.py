"""Stage 166 C1 — offline catalog pull honesty + client cache module."""

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
async def test_sync_pull_catalog_stock_non_authoritative_c1(client):
    ac, seed = client
    headers = await _super(ac, seed)
    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Catalog device", "platform": "web"},
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
    assert payload.get("as_of")
    assert isinstance(payload.get("products"), list)
    if payload["products"]:
        p0 = payload["products"][0]
        assert "stock_qty" in p0
        assert "available_qty" in p0


def test_offline_catalog_module_and_pos_ui_c1():
    catalog = (ROOT / "frontend/lib/offlineCatalog.ts").read_text(encoding="utf-8")
    assert "stock_authoritative" in catalog
    assert "searchOfflineCatalog" in catalog
    assert "refreshOfflineCatalog" in catalog
    assert "ribdigi-offline-catalog" in catalog
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "offlineCatalog" in pos
    assert "stale" in pos.lower() or "non-authoritative" in pos.lower()
    assert "Refresh offline catalog" in pos
    engine = (ROOT / "backend/app/sync_engine.py").read_text(encoding="utf-8")
    assert 'stock_authoritative": False' in engine or "stock_authoritative\": False" in engine
