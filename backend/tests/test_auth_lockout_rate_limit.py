"""Account lockout + per-IP sign-in limits (app/auth_guard.py).

Covers: good and wrong sign-ins, lockout on the 5th wrong try, refusal while locked with the same
answer as a wrong password, expiry, the 15/30/60/120 ladder and its reset, counters cleared by a
good sign-in, per-IP buckets (many accounts from one IP, forged X-Forwarded-For, X-Tenant-ID
rotation), one account from many IPs, simultaneous tries, Redis down, tenant isolation, admin
unlock permissions, audit rows, password-reset / OTP buckets, and 2FA guesses counting.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pyotp
import pytest
from sqlalchemy import select

from app import auth_guard
from app import models as m
from app.auth_guard import GENERIC_LOGIN_FAILURE
from app.config import settings
from app.rate_limit import rate_limiter
from app.security import hash_password
from tests.conftest import auth_headers

LOGIN = "/api/v1/auth/login"
GOOD = "SecurePass123!"
BAD = "WrongPass123!"


def _body(email="cashier@alpha.example.com", password=GOOD, tenant="alpha", **extra):
    return {"email": email, "password": password, "tenant_id": tenant, **extra}


async def _user(db_session, email="cashier@alpha.example.com") -> m.User:
    db_session.expire_all()
    return (await db_session.execute(select(m.User).where(m.User.email == email))).scalars().first()


async def _fail(ac, n, **kw):
    out = []
    for _ in range(n):
        out.append(await ac.post(LOGIN, json=_body(password=BAD, **kw)))
    return out


async def _actions(db_session, user_id: str) -> list[str]:
    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(m.AuditLog.action)
            .where(m.AuditLog.module == "auth", m.AuditLog.entity_id == user_id)
            .order_by(m.AuditLog.created_at)
        )
    ).scalars().all()
    return list(rows)


@pytest.fixture
def ip_limits(monkeypatch):
    """Turn the IP buckets on (the shared client fixture turns all limits off)."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 1000)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1000)
    monkeypatch.setattr(settings, "RATE_LIMIT_READ_PER_MINUTE", 1000)
    rate_limiter.reset_for_tests()
    yield
    rate_limiter.reset_for_tests()


def _ip(addr: str) -> dict:
    return {"X-Forwarded-For": addr}


# ---------------------------------------------------------------- 1, 2


@pytest.mark.asyncio
async def test_good_sign_in_and_wrong_password(client, db_session):
    ac, _ = client
    ok = await ac.post(LOGIN, json=_body())
    assert ok.status_code == 200, ok.text

    bad = await ac.post(LOGIN, json=_body(password=BAD))
    assert bad.status_code == 401
    assert bad.json()["detail"] == GENERIC_LOGIN_FAILURE
    assert BAD not in bad.text
    user = await _user(db_session)
    assert user.failed_login_attempts == 1
    assert user.last_failed_login_at is not None
    assert user.locked_until is None


# ---------------------------------------------------------------- 3, 4, 5 (no enumeration)


@pytest.mark.asyncio
async def test_fifth_wrong_try_locks_and_answers_like_a_wrong_password(client, db_session):
    ac, _ = client
    replies = await _fail(ac, 4)
    assert all(r.status_code == 401 for r in replies)
    assert (await _user(db_session)).locked_until is None

    fifth = (await _fail(ac, 1))[0]
    assert fifth.status_code == 401
    user = await _user(db_session)
    assert user.locked_until is not None
    minutes = (user.locked_until - user.locked_at).total_seconds() / 60
    assert round(minutes) == 15
    assert user.lockout_count == 1
    assert user.failed_login_attempts == 0

    locked = await ac.post(LOGIN, json=_body())  # right password, still refused
    unknown = await ac.post(LOGIN, json=_body(email="nobody@alpha.example.com"))
    wrong = await ac.post(LOGIN, json=_body(email="mgr@alpha.example.com", password=BAD))
    assert locked.status_code == unknown.status_code == wrong.status_code == 401
    assert locked.json() == unknown.json() == wrong.json() == {"detail": GENERIC_LOGIN_FAILURE}
    for r in (locked, unknown, wrong):
        assert "lock" not in r.text.lower().replace("several unsuccessful", "")
        assert "retry-after" not in {k.lower() for k in r.headers}

    # Staff (no company code) sign-in gives the same answer for a locked or unknown account.
    staff_locked = await ac.post("/api/v1/auth/staff-login", json={"login": "cashier@alpha.example.com", "password": GOOD})
    staff_unknown = await ac.post("/api/v1/auth/staff-login", json={"login": "ghost@nowhere.example.com", "password": GOOD})
    assert staff_locked.status_code == staff_unknown.status_code == 401
    assert staff_locked.json() == staff_unknown.json()

    # Tries while locked are not counted toward the next lockout.
    assert (await _user(db_session)).failed_login_attempts == 0


@pytest.mark.asyncio
async def test_lock_expires_by_itself(client, db_session):
    ac, _ = client
    await _fail(ac, 5)
    user = await _user(db_session)
    user.locked_until = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    ok = await ac.post(LOGIN, json=_body())
    assert ok.status_code == 200, ok.text
    user = await _user(db_session)
    assert user.locked_until is None
    assert user.failed_login_attempts == 0
    assert user.lockout_count == 0


# ---------------------------------------------------------------- 6


@pytest.mark.asyncio
async def test_lockout_ladder_15_30_60_120_then_repeats(client, db_session):
    ac, _ = client
    seen = []
    for _round in range(5):
        await _fail(ac, 5)
        user = await _user(db_session)
        seen.append(round((user.locked_until - user.locked_at).total_seconds() / 60))
        user.locked_until = datetime.utcnow() - timedelta(seconds=1)  # let it expire, keep the ladder
        await db_session.commit()
    assert seen == [15, 30, 60, 120, 120]


@pytest.mark.asyncio
async def test_ladder_starts_over_after_a_quiet_day(client, db_session):
    ac, _ = client
    await _fail(ac, 5)
    user = await _user(db_session)
    user.locked_until = datetime.utcnow() - timedelta(seconds=1)
    user.locked_at = datetime.utcnow() - timedelta(hours=25)
    await db_session.commit()
    await _fail(ac, 5)
    user = await _user(db_session)
    assert round((user.locked_until - user.locked_at).total_seconds() / 60) == 15
    assert user.lockout_count == 1


# ---------------------------------------------------------------- 7


@pytest.mark.asyncio
async def test_good_sign_in_clears_the_counter(client, db_session):
    ac, _ = client
    await _fail(ac, 4)
    assert (await ac.post(LOGIN, json=_body())).status_code == 200
    assert (await _user(db_session)).failed_login_attempts == 0
    await _fail(ac, 4)
    assert (await _user(db_session)).locked_until is None


# ---------------------------------------------------------------- 8, 9, 11


@pytest.mark.asyncio
async def test_five_failed_tries_per_ip_then_429_before_the_password(client, ip_limits):
    ac, _ = client
    for _ in range(5):
        r = await ac.post(LOGIN, json=_body(email="mgr@alpha.example.com", password=BAD), headers=_ip("41.66.1.2"))
        assert r.status_code == 401
    # Even the right password for another account is refused now: no more guesses from this IP.
    sixth = await ac.post(LOGIN, json=_body(), headers=_ip("41.66.1.2"))
    assert sixth.status_code == 429
    assert int(sixth.headers["Retry-After"]) >= 1
    assert sixth.json()["detail"]["code"] == "RATE_LIMIT_EXCEEDED"
    # Another network is unaffected.
    other = await ac.post(LOGIN, json=_body(), headers=_ip("41.66.9.9"))
    assert other.status_code == 200


@pytest.mark.asyncio
async def test_a_shop_sharing_one_ip_can_sign_everyone_in(client, ip_limits, monkeypatch):
    """Good sign-ins do not use up the 5 failed tries; only the higher all-requests cap applies."""
    ac, _ = client
    monkeypatch.setattr(settings, "AUTH_IP_LOGIN_REQUEST_LIMIT", 8)
    for i in range(8):
        email = ["cashier@alpha.example.com", "mgr@alpha.example.com", "admin@alpha.example.com"][i % 3]
        r = await ac.post(LOGIN, json=_body(email=email), headers=_ip("41.66.1.9"))
        assert r.status_code == 200, (i, r.text)
    capped = await ac.post(LOGIN, json=_body(), headers=_ip("41.66.1.9"))
    assert capped.status_code == 429


@pytest.mark.asyncio
async def test_rotating_usernames_and_tenant_header_shares_one_bucket(client, ip_limits):
    ac, seed = client
    emails = ["cashier@alpha.example.com", "mgr@alpha.example.com", "admin@alpha.example.com", "x@alpha.example.com", "y@alpha.example.com"]
    for i, email in enumerate(emails):
        r = await ac.post(
            LOGIN, json=_body(email=email, password=BAD),
            headers={**_ip("41.66.1.3"), "X-Tenant-ID": f"00000000-0000-0000-0000-00000000000{i}"},
        )
        assert r.status_code == 401
    r = await ac.post(LOGIN, json=_body(email="z@alpha.example.com", password=BAD), headers={**_ip("41.66.1.3"), "X-Tenant-ID": seed["t2"].id})
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_forged_forwarded_for_does_not_open_new_buckets(client, ip_limits):
    ac, _ = client
    for i in range(5):
        r = await ac.post(LOGIN, json=_body(password=BAD), headers=_ip(f"6.6.6.{i}, 41.66.1.4"))
        assert r.status_code == 401
    r = await ac.post(LOGIN, json=_body(password=BAD), headers=_ip("9.9.9.9, 41.66.1.4"))
    assert r.status_code == 429


def test_trusted_proxy_cidr_and_ipv6_grouping(monkeypatch):
    from app.middleware import client_ip_from_request

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.0/8,172.18.0.0/16")
    req = SimpleNamespace(headers={"x-forwarded-for": "6.6.6.6, 41.66.1.2, 10.1.2.3, 172.18.0.5"}, client=SimpleNamespace(host="172.18.0.7"))
    assert client_ip_from_request(req) == "41.66.1.2"
    assert auth_guard.ip_bucket_key("2001:db8:1:2:aaaa::1") == auth_guard.ip_bucket_key("2001:db8:1:2:bbbb::9")
    assert auth_guard.ip_bucket_key("2001:db8:1:3::1") != auth_guard.ip_bucket_key("2001:db8:1:2::1")
    assert auth_guard.ip_bucket_key("::ffff:41.66.1.2") == "41.66.1.2"


def test_coarse_auth_bucket_ignores_tenant_header():
    from app.middleware import RateLimitMiddleware

    mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
    auth_req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/auth/login"), headers={"x-tenant-id": "abc"})
    api_req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/products"), headers={"x-tenant-id": "abc"})
    assert mw._tenant_scope(auth_req) == "anon"
    assert mw._tenant_scope(api_req) == "abc"


@pytest.mark.asyncio
async def test_good_sign_in_does_not_empty_the_ip_bucket(client, ip_limits):
    ac, _ = client
    for _ in range(4):
        await ac.post(LOGIN, json=_body(email="mgr@alpha.example.com", password=BAD), headers=_ip("41.66.1.5"))
    assert (await ac.post(LOGIN, json=_body(email="admin@alpha.example.com"), headers=_ip("41.66.1.5"))).status_code == 200
    # Still 4 failed tries on this IP after the good sign-in: the 5th fills the bucket.
    assert (await ac.post(LOGIN, json=_body(email="x@alpha.example.com", password=BAD), headers=_ip("41.66.1.5"))).status_code == 401
    assert (await ac.post(LOGIN, json=_body(email="admin@alpha.example.com"), headers=_ip("41.66.1.5"))).status_code == 429


# ---------------------------------------------------------------- 10


@pytest.mark.asyncio
async def test_one_account_from_many_ips_still_locks(client, db_session, ip_limits):
    ac, _ = client
    for i in range(5):
        r = await ac.post(LOGIN, json=_body(password=BAD), headers=_ip(f"41.70.{i}.1"))
        assert r.status_code == 401
    user = await _user(db_session)
    assert user.locked_until is not None
    fresh_ip = await ac.post(LOGIN, json=_body(), headers=_ip("41.80.0.1"))
    assert fresh_ip.status_code == 401
    assert fresh_ip.json()["detail"] == GENERIC_LOGIN_FAILURE


# ---------------------------------------------------------------- 12


@pytest.mark.asyncio
async def test_simultaneous_wrong_tries_lock_once(client, db_session):
    ac, _ = client
    replies = await asyncio.gather(*[ac.post(LOGIN, json=_body(password=BAD)) for _ in range(12)])
    assert all(r.status_code == 401 for r in replies)
    user = await _user(db_session)
    assert user.locked_until is not None
    # 12 tries: one lock at the 5th; the rest either counted toward the next (≤4) or refused while locked.
    assert user.lockout_count == 1
    assert user.failed_login_attempts < settings.AUTH_LOCKOUT_THRESHOLD
    assert (await _actions(db_session, user.id)).count("account_locked") == 1


@pytest.mark.asyncio
async def test_lock_guard_is_atomic_at_the_service_level(client, db_session):
    """Two counted failures that both see the threshold: only one takes the lock."""
    _ac, _ = client
    user = await _user(db_session)
    user.failed_login_attempts = settings.AUTH_LOCKOUT_THRESHOLD - 1
    await db_session.commit()
    first = await auth_guard.register_failure(db_session, user, request=None)
    second = await auth_guard.register_failure(db_session, user, request=None)
    assert first is True
    assert second is False  # already locked: not counted, not re-locked
    user = await _user(db_session)
    assert user.lockout_count == 1


# ---------------------------------------------------------------- 13


class _DeadRedis:
    async def eval(self, *a, **k):
        raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_redis_down_keeps_limiting_in_memory(client, db_session, ip_limits, monkeypatch):
    ac, _ = client
    rate_limiter._redis = _DeadRedis()
    rate_limiter._backend = "redis"
    rate_limiter._redis_expected = True
    rate_limiter._init_attempted = True
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "auto")
    monkeypatch.setattr("app.rate_limit.REDIS_RETRY_SECONDS", 3600)
    for _ in range(5):
        assert (await ac.post(LOGIN, json=_body(email="mgr@alpha.example.com", password=BAD), headers=_ip("41.66.2.1"))).status_code == 401
    assert (await ac.post(LOGIN, json=_body(), headers=_ip("41.66.2.1"))).status_code == 429
    # Account lockout lives in the database and is unaffected by Redis.
    assert (await _user(db_session, "mgr@alpha.example.com")).locked_until is not None


@pytest.mark.asyncio
async def test_redis_down_fail_closed_returns_503(client, ip_limits, monkeypatch):
    ac, _ = client
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_FAIL_CLOSED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "auto")
    monkeypatch.setattr("app.rate_limit.REDIS_RETRY_SECONDS", 3600)
    rate_limiter._redis = _DeadRedis()
    rate_limiter._backend = "redis"
    rate_limiter._redis_expected = True
    rate_limiter._init_attempted = True
    r = await ac.post(LOGIN, json=_body(), headers=_ip("41.66.2.2"))
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "30"
    assert r.json()["detail"]["code"] == "AUTH_TEMPORARILY_UNAVAILABLE"


# ---------------------------------------------------------------- 14


@pytest.mark.asyncio
async def test_lock_is_per_account_and_per_company(client, db_session):
    ac, seed = client
    twin = m.User(
        tenant_id=seed["t2"].id, email="cashier@alpha.example.com", full_name="Twin",
        password_hash=hash_password(GOOD), role="cashier", email_verified=True,
    )
    db_session.add(twin)
    await db_session.commit()

    await _fail(ac, 5)  # locks the alpha account
    assert (await ac.post(LOGIN, json=_body(tenant="beta"))).status_code == 200
    assert (await ac.post(LOGIN, json=_body(email="cashier@beta.example.com", tenant="beta"))).status_code == 200

    # Alpha's admin cannot see or unlock beta's account, and vice versa.
    alpha_admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.post(f"/api/v1/users/{twin.id}/unlock", headers=alpha_admin)).status_code == 404
    assert (await ac.get(f"/api/v1/users/{twin.id}/security", headers=alpha_admin)).status_code == 404
    listed = await ac.get("/api/v1/users/security/locked", headers=alpha_admin)
    assert listed.status_code == 200
    ids = {row["user_id"] for row in listed.json()["data"]}
    assert seed["u1"].id in ids and twin.id not in ids


# ---------------------------------------------------------------- 15


@pytest.mark.asyncio
async def test_admin_unlock_permissions(client, db_session):
    ac, seed = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await _fail(ac, 5)

    assert (await ac.post(f"/api/v1/users/{seed['u1'].id}/unlock", headers=mgr)).status_code == 403
    assert (await ac.get("/api/v1/users/security/locked", headers=mgr)).status_code == 403
    assert (await ac.get("/api/v1/users/security/events", headers=mgr)).status_code == 403
    # Company admins are not platform staff.
    assert (await ac.post(f"/api/v1/platform/tenants/beta/users/{seed['u2'].id}/unlock", headers=admin)).status_code == 403

    state = await ac.get(f"/api/v1/users/{seed['u1'].id}/security", headers=admin)
    assert state.status_code == 200
    assert state.json()["data"]["locked"] is True
    assert state.json()["data"]["locked_until"].endswith("Z")

    r = await ac.post(f"/api/v1/users/{seed['u1'].id}/unlock", headers=admin, json={"note": "Called the cashier"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["locked"] is False
    assert (await ac.post(LOGIN, json=_body())).status_code == 200


@pytest.mark.asyncio
async def test_platform_staff_can_unlock_any_company(client, db_session, monkeypatch):
    ac, seed = client
    await _fail(ac, 5, email="cashier@beta.example.com", tenant="beta")
    seed["super"].totp_enabled = False
    await db_session.commit()
    sup = await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(f"/api/v1/platform/tenants/beta/users/{seed['u2'].id}/unlock", headers=sup)
    assert r.status_code == 200, r.text
    # Wrong company reference for that user → 404, never a cross-company unlock.
    assert (await ac.post(f"/api/v1/platform/tenants/alpha/users/{seed['u2'].id}/unlock", headers=sup)).status_code == 404
    assert (await ac.post(LOGIN, json=_body(email="cashier@beta.example.com", tenant="beta"))).status_code == 200


# ---------------------------------------------------------------- 16


@pytest.mark.asyncio
async def test_audit_trail_without_secrets(client, db_session):
    ac, seed = client
    uid, tid = seed["u1"].id, seed["t1"].id
    await _fail(ac, 5)
    await ac.post(LOGIN, json=_body())  # blocked while locked
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await ac.post(f"/api/v1/users/{uid}/unlock", headers=admin)
    await ac.post(LOGIN, json=_body())
    actions = await _actions(db_session, uid)
    for needed in ("login_failed", "account_locked", "login_blocked_locked", "account_unlocked", "login"):
        assert needed in actions, actions

    rows = (
        await db_session.execute(select(m.AuditLog).where(m.AuditLog.module == "auth", m.AuditLog.tenant_id == tid))
    ).scalars().all()
    for row in rows:
        blob = repr(row.details).lower()
        assert BAD.lower() not in blob and GOOD.lower() not in blob
        assert "password_hash" not in blob
    failed = next(r for r in rows if r.action == "login_failed")
    assert failed.ip_address and failed.user_agent is not None

    events = await ac.get(f"/api/v1/users/security/events?user_id={uid}", headers=admin)
    assert events.status_code == 200
    assert {"account_locked", "account_unlocked"} <= {e["action"] for e in events.json()["data"]}


def test_metrics_expose_auth_counters():
    from app import metrics

    auth_guard._bump("auth_account_locked", "password")
    assert "ribdigi_auth_security_events_total" in metrics.render_prometheus()


# ---------------------------------------------------------------- 17


@pytest.mark.asyncio
async def test_password_reset_requests_are_limited_and_reset_lifts_lock(client, db_session, ip_limits):
    ac, _ = client
    await _fail(ac, 5)
    rate_limiter.reset_for_tests()
    tokens = []
    for _ in range(3):
        r = await ac.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "cashier@alpha.example.com", "tenant_id": "alpha"},
            headers=_ip("41.66.3.1"),
        )
        assert r.status_code == 200, r.text
        tokens.append(r.json()["data"].get("reset_token"))
    fourth = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "someone-else@alpha.example.com", "tenant_id": "alpha"},
        headers=_ip("41.66.3.1"),
    )
    assert fourth.status_code == 429
    assert "Retry-After" in fourth.headers

    done = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": tokens[-1], "new_password": "BrandNewPass456!"},
        headers=_ip("41.66.3.2"),
    )
    assert done.status_code == 200, done.text
    assert (await _user(db_session)).locked_until is None
    ok = await ac.post(LOGIN, json=_body(password="BrandNewPass456!"), headers=_ip("41.66.3.3"))
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_otp_request_and_verify_buckets(client, ip_limits):
    ac, _ = client
    for _ in range(3):
        r = await ac.post(
            "/api/v1/auth/resend-verification",
            json={"email": "cashier@alpha.example.com", "tenant_id": "alpha"},
            headers=_ip("41.66.4.1"),
        )
        assert r.status_code == 200, r.text
    assert (
        await ac.post(
            "/api/v1/auth/resend-verification",
            json={"email": "cashier@alpha.example.com", "tenant_id": "alpha"},
            headers=_ip("41.66.4.1"),
        )
    ).status_code == 429

    for _ in range(5):
        r = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": "abc.def.ghi", "code": "123456"}, headers=_ip("41.66.4.2"))
        assert r.status_code == 401
    r = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": "abc.def.ghi", "code": "123456"}, headers=_ip("41.66.4.2"))
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_second_factor_guesses_lock_the_account(client, db_session, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "LOGIN_2FA_ENABLED", True)
    body = _body(email="super@alpha.example.com")
    first = await ac.post(LOGIN, json=body)
    assert first.status_code == 200 and first.json()["data"]["requires_2fa"]
    challenge = first.json()["data"]["challenge_token"]
    for _ in range(4):
        r = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": challenge, "code": "000000"})
        assert r.status_code == 401
    # Password again (a new challenge) must not reset the guess counter.
    again = await ac.post(LOGIN, json=body)
    assert again.json()["data"]["requires_2fa"]
    assert (await _user(db_session, "super@alpha.example.com")).failed_login_attempts == 4
    r = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": challenge, "code": "000000"})
    assert r.status_code == 401
    assert (await _user(db_session, "super@alpha.example.com")).locked_until is not None

    good_code = pyotp.TOTP(seed["super_totp_secret"]).now()
    blocked = await ac.post("/api/v1/auth/2fa/verify", json={"challenge_token": challenge, "code": good_code})
    assert blocked.status_code == 401
    assert (await ac.post(LOGIN, json=body)).json()["detail"] == GENERIC_LOGIN_FAILURE


@pytest.mark.asyncio
async def test_storefront_register_and_login_are_ip_limited(client, ip_limits):
    ac, _ = client
    statuses = []
    for i in range(6):
        r = await ac.post(
            "/api/v1/storefront/account/register",
            json={"name": "Shopper", "email": f"s{i}@example.com", "password": "ShopperPass123!"},
            headers=_ip("41.66.5.1"),
        )
        statuses.append(r.status_code)
    # The storefront itself may refuse (no shop on this host), but the 6th never reaches it.
    assert statuses[-1] == 429
    assert all(s != 429 for s in statuses[:5])


# ---------------------------------------------------------------- real Redis (opt-in)


@pytest.mark.asyncio
async def test_two_workers_share_one_redis_count(monkeypatch):
    """Set REDIS_TEST_URL to a throwaway Redis DB to run. Two limiters = two workers."""
    import os
    import uuid

    url = os.environ.get("REDIS_TEST_URL", "").strip()
    if not url:
        pytest.skip("REDIS_TEST_URL not set")
    from app.rate_limit import RateLimiter

    monkeypatch.setattr(settings, "REDIS_URL", url)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "RATE_LIMIT_REDIS_PREFIX", f"ribdigi:test:{uuid.uuid4().hex}")
    a, b = RateLimiter(), RateLimiter()
    key = "auth:login:41.66.7.7"
    results = await asyncio.gather(*[(a if i % 2 else b).allow(key, 5, 60) for i in range(12)])
    assert a.backend == b.backend == "redis"
    assert sum(1 for ok, _r, _rem in results if ok) == 5  # atomic: never more than the limit
    blocked = [r for ok, r, _rem in results if not ok]
    assert blocked and all(1 <= r <= 61 for r in blocked)
