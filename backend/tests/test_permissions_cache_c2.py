"""Stage 7 C2: Redis app-cache for resolved user permissions (1h TTL)."""

from __future__ import annotations

import pyotp
import pytest

from app import cache as cache_svc
from app.cache import AppCache
from app.security import resolve_user_permissions
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
    monkeypatch.setattr(cache_svc.settings, "CACHE_PERMISSIONS_TTL_SECONDS", 3600)
    monkeypatch.setattr("app.config.settings.CACHE_ENABLED", True)
    monkeypatch.setattr("app.config.settings.CACHE_PERMISSIONS_TTL_SECONDS", 3600)
    yield fake
    c.reset_for_tests()


@pytest.mark.asyncio
async def test_permissions_key_is_tenant_scoped():
    c = AppCache()
    key = c.permissions_key("t-1", "u-9")
    assert key.endswith(":perms:t-1:u-9")
    assert "t-1" in key and "u-9" in key


@pytest.mark.asyncio
async def test_resolve_user_permissions_hit_and_ttl(client, fake_cache, db_session):
    ac, seed = client
    user = seed["u1"]
    first = await resolve_user_permissions(db_session, user)
    key = cache_svc.app_cache.permissions_key(user.tenant_id, user.id)
    assert key in fake_cache.store
    assert fake_cache.ttls[key] == 3600
    assert isinstance(first, dict)
    assert "pos" in first or "*" in first
    sets_after = fake_cache.sets

    second = await resolve_user_permissions(db_session, user)
    assert second == first
    assert fake_cache.sets == sets_after


@pytest.mark.asyncio
async def test_me_uses_permissions_cache(client, fake_cache):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    r1 = await ac.get("/api/v1/me", headers=headers)
    assert r1.status_code == 200, r1.text
    key = cache_svc.app_cache.permissions_key(seed["t1"].id, seed["u1"].id)
    assert key in fake_cache.store
    assert fake_cache.ttls[key] == 3600
    sets_after = fake_cache.sets

    r2 = await ac.get("/api/v1/me", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["permissions"] == r1.json()["data"]["permissions"]
    assert fake_cache.sets == sets_after


@pytest.mark.asyncio
async def test_role_change_invalidates_permissions_cache(client, fake_cache):
    ac, seed = client
    cashier_headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    warm = await ac.get("/api/v1/me", headers=cashier_headers)
    assert warm.status_code == 200
    key = cache_svc.app_cache.permissions_key(seed["t1"].id, seed["u1"].id)
    assert key in fake_cache.store

    admin = await _admin(ac, seed)
    patched = await ac.patch(
        f"/api/v1/users/{seed['u1'].id}",
        headers=admin,
        json={"role": "sales_officer"},
    )
    assert patched.status_code == 200, patched.text
    assert key not in fake_cache.store

    again = await ac.get("/api/v1/me", headers=cashier_headers)
    assert again.status_code == 200
    assert again.json()["data"]["role"] == "sales_officer"
    assert key in fake_cache.store


@pytest.mark.asyncio
async def test_custom_role_update_invalidates_assigned_users(client, fake_cache):
    ac, seed = client
    admin = await _admin(ac, seed)
    created_role = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "slug": "cache_role",
            "label": "Cache Role",
            "permissions": {
                "dashboard": ["read"],
                "pos": ["read", "write"],
                "notifications": ["read"],
                "security": ["read", "write"],
            },
            "record_scope": "own",
        },
    )
    assert created_role.status_code == 200, created_role.text

    # Reuse verified seed cashier so login is allowed without email-verify fixture.
    assigned = await ac.patch(
        f"/api/v1/users/{seed['u1'].id}",
        headers=admin,
        json={"role": "cache_role"},
    )
    assert assigned.status_code == 200, assigned.text

    user_headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    warm = await ac.get("/api/v1/me", headers=user_headers)
    assert warm.status_code == 200
    key = cache_svc.app_cache.permissions_key(seed["t1"].id, seed["u1"].id)
    assert key in fake_cache.store

    updated = await ac.patch(
        "/api/v1/roles/cache_role",
        headers=admin,
        json={
            "permissions": {
                "dashboard": ["read"],
                "inventory": ["read"],
                "notifications": ["read"],
                "security": ["read", "write"],
            }
        },
    )
    assert updated.status_code == 200, updated.text
    assert key not in fake_cache.store


@pytest.mark.asyncio
async def test_permissions_soft_fail_when_cache_disabled(client, monkeypatch):
    ac, seed = client
    c = cache_svc.app_cache
    c.reset_for_tests()
    monkeypatch.setattr(cache_svc.settings, "CACHE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.CACHE_ENABLED", False)

    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/me", headers=headers)
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["data"]["permissions"], dict)
    c.reset_for_tests()
