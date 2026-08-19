"""Stage 6 P2: Redis app-data cache for dashboard and catalog."""

from __future__ import annotations

import json

import pyotp
import pytest

from app import cache as cache_svc
from app.cache import AppCache
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.gets = 0
        self.sets = 0

    async def ping(self):
        return True

    async def get(self, key: str):
        self.gets += 1
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.sets += 1
        self.store[key] = value
        self.ttls[key] = int(ttl)
        return True

    async def delete(self, *keys: str):
        for key in keys:
            self.store.pop(key, None)
            self.ttls.pop(key, None)
        return len(keys)


@pytest.fixture
def fake_cache(monkeypatch):
    fake = FakeRedis()
    c = cache_svc.app_cache
    c.reset_for_tests()
    c._init_attempted = True
    c._backend = "redis"
    c._redis = fake
    monkeypatch.setattr(cache_svc.settings, "CACHE_ENABLED", True)
    monkeypatch.setattr(cache_svc.settings, "CACHE_BACKEND", "redis")
    monkeypatch.setattr(cache_svc.settings, "CACHE_DASHBOARD_TTL_SECONDS", 300)
    monkeypatch.setattr(cache_svc.settings, "CACHE_CATALOG_TTL_SECONDS", 600)
    yield fake
    c.reset_for_tests()


@pytest.mark.asyncio
async def test_app_cache_unit_get_set_delete():
    c = AppCache()
    c.reset_for_tests()
    c._init_attempted = True
    c._backend = "memory"
    key = c.dashboard_key("t-1")
    assert await c.get_json(key) is None
    assert await c.set_json(key, {"products": 3}, ttl_seconds=60)
    assert await c.get_json(key) == {"products": 3}
    await c.invalidate_dashboard("t-1")
    assert await c.get_json(key) is None
    c.reset_for_tests()


@pytest.mark.asyncio
async def test_dashboard_and_products_cache_hit(client, fake_cache):
    ac, seed = client
    headers = await _admin(ac, seed)

    first = await ac.get("/api/v1/dashboard", headers=headers)
    assert first.status_code == 200, first.text
    dash_key = cache_svc.app_cache.dashboard_key(seed["t1"].id)
    assert dash_key in fake_cache.store
    assert fake_cache.ttls[dash_key] == 300
    sets_after_first = fake_cache.sets

    second = await ac.get("/api/v1/dashboard", headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["products"] == first.json()["data"]["products"]
    assert fake_cache.sets == sets_after_first  # served from cache

    p1 = await ac.get("/api/v1/products", headers=headers)
    assert p1.status_code == 200, p1.text
    products_key = cache_svc.app_cache.products_key(seed["t1"].id)
    assert products_key in fake_cache.store
    assert fake_cache.ttls[products_key] == 600
    sets_mid = fake_cache.sets

    p2 = await ac.get("/api/v1/products", headers=headers)
    assert p2.status_code == 200
    assert len(p2.json()["data"]) == len(p1.json()["data"])
    assert fake_cache.sets == sets_mid


@pytest.mark.asyncio
async def test_categories_flat_vs_tree_keys(client, fake_cache):
    ac, seed = client
    headers = await _admin(ac, seed)

    flat = await ac.get("/api/v1/catalog/categories", headers=headers)
    tree = await ac.get("/api/v1/catalog/categories?tree=true", headers=headers)
    assert flat.status_code == 200, flat.text
    assert tree.status_code == 200, tree.text
    flat_key = cache_svc.app_cache.categories_key(seed["t1"].id, tree=False)
    tree_key = cache_svc.app_cache.categories_key(seed["t1"].id, tree=True)
    assert flat_key in fake_cache.store
    assert tree_key in fake_cache.store
    assert flat_key != tree_key


@pytest.mark.asyncio
async def test_product_create_invalidates_catalog_and_dashboard(client, fake_cache):
    ac, seed = client
    headers = await _admin(ac, seed)

    await ac.get("/api/v1/dashboard", headers=headers)
    await ac.get("/api/v1/products", headers=headers)
    dash_key = cache_svc.app_cache.dashboard_key(seed["t1"].id)
    products_key = cache_svc.app_cache.products_key(seed["t1"].id)
    assert dash_key in fake_cache.store
    assert products_key in fake_cache.store

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Cached Widget",
            "sku": "CACHE-P2-1",
            "selling_price": 9,
            "cost_price": 4,
            "stock_qty": 0,
        },
    )
    assert created.status_code == 200, created.text
    assert dash_key not in fake_cache.store
    assert products_key not in fake_cache.store

    # Refill cache; new product must appear
    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200
    skus = {row["sku"] for row in listed.json()["data"]}
    assert "CACHE-P2-1" in skus


@pytest.mark.asyncio
async def test_tenant_isolation_of_cache_keys(client, fake_cache):
    ac, seed = client
    headers = await _admin(ac, seed)
    await ac.get("/api/v1/products", headers=headers)
    t1_key = cache_svc.app_cache.products_key(seed["t1"].id)
    t2_key = cache_svc.app_cache.products_key(seed["t2"].id)
    assert t1_key in fake_cache.store
    assert t2_key not in fake_cache.store
    # Poison t2 key with t1 payload — must not be returned for t1
    fake_cache.store[t2_key] = json.dumps([{"sku": "LEAK"}])
    listed = await ac.get("/api/v1/products", headers=headers)
    skus = {row["sku"] for row in listed.json()["data"]}
    assert "LEAK" not in skus


@pytest.mark.asyncio
async def test_cache_disabled_passthrough(client, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    cache_svc.app_cache.reset_for_tests()
    monkeypatch.setattr(cache_svc.settings, "CACHE_ENABLED", False)
    res = await ac.get("/api/v1/dashboard", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["products"] >= 1
    cache_svc.app_cache.reset_for_tests()
