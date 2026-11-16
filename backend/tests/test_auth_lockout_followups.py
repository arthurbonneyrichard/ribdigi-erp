"""Sign-in protection follow-ups: company codes cannot be probed, shared shop IPs, storefront shopper
lockout, timezone-aware lock times, and X-Forwarded-For believed only from proxies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import auth_guard
from app import models as m
from app.auth_guard import GENERIC_LOGIN_FAILURE
from app.config import settings
from app.security import hash_password
from tests.conftest import auth_headers
from tests.test_auth_lockout_rate_limit import BAD, GOOD, LOGIN, _body, _fail, _ip, _user, ip_limits  # noqa: F401


# ---------------------------------------------------------------- company codes cannot be probed


@pytest.mark.asyncio
async def test_unknown_or_suspended_company_answers_like_a_wrong_password(client, db_session):
    ac, seed = client
    unknown = await ac.post(LOGIN, json=_body(tenant="no-such-company"))
    wrong = await ac.post(LOGIN, json=_body(password=BAD))
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": GENERIC_LOGIN_FAILURE}

    tenant = await db_session.get(m.Tenant, seed["t2"].id)
    tenant.status = "suspended"
    await db_session.commit()
    beta_wrong = await ac.post(LOGIN, json=_body(email="cashier@beta.example.com", tenant="beta", password=BAD))
    beta_unknown = await ac.post(LOGIN, json=_body(email="ghost@beta.example.com", tenant="beta"))
    assert beta_wrong.json() == beta_unknown.json() == {"detail": GENERIC_LOGIN_FAILURE}
    # Only the real owner of a password hears that the company is suspended.
    beta_right = await ac.post(LOGIN, json=_body(email="cashier@beta.example.com", tenant="beta"))
    assert beta_right.status_code == 403
    assert "suspended" in str(beta_right.json()["detail"]).lower()


@pytest.mark.asyncio
async def test_reset_and_resend_reply_the_same_for_unknown_company_and_account(client, monkeypatch):
    ac, _ = client
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEBUG", False)
    replies = [
        await ac.post("/api/v1/auth/password-reset-request", json={"email": e, "tenant_id": t})
        for e, t in (
            ("cashier@alpha.example.com", "alpha"),
            ("ghost@alpha.example.com", "alpha"),
            ("cashier@alpha.example.com", "no-such-company"),
        )
    ]
    assert {r.status_code for r in replies} == {200}
    assert len({r.text for r in replies}) == 1, [r.text for r in replies]

    resends = [
        await ac.post("/api/v1/auth/resend-verification", json={"email": e, "tenant_id": t})
        for e, t in (("cashier@alpha.example.com", "alpha"), ("x@alpha.example.com", "no-such-company"))
    ]
    assert {r.status_code for r in resends} == {200}
    assert len({r.text for r in resends}) == 1


@pytest.mark.asyncio
async def test_staff_sign_in_hides_an_email_shared_by_two_companies(client, db_session):
    ac, seed = client
    db_session.add(
        m.User(
            tenant_id=seed["t2"].id, email="cashier@alpha.example.com", full_name="Twin",
            password_hash=hash_password(GOOD), role="cashier", email_verified=True,
        )
    )
    await db_session.commit()
    staff = "/api/v1/auth/staff-login"
    wrong = await ac.post(staff, json={"login": "cashier@alpha.example.com", "password": BAD})
    unknown = await ac.post(staff, json={"login": "nobody@alpha.example.com", "password": BAD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    # The person who knows the password is told to use a username instead.
    right = await ac.post(staff, json={"login": "cashier@alpha.example.com", "password": GOOD})
    assert right.status_code == 409
    assert right.json()["detail"]["code"] == "LOGIN_NOT_UNIQUE"


@pytest.mark.asyncio
async def test_unknown_company_tries_fill_the_ip_failure_bucket(client, ip_limits):
    ac, _ = client
    for i in range(5):
        r = await ac.post(LOGIN, json=_body(tenant=f"guess-{i}"), headers=_ip("41.66.6.1"))
        assert r.status_code == 401
    assert (await ac.post(LOGIN, json=_body(), headers=_ip("41.66.6.1"))).status_code == 429


# ---------------------------------------------------------------- storefront shoppers


@pytest.mark.asyncio
async def test_shopper_lockout_and_staff_unlock(client, db_session, monkeypatch):
    from fastapi import HTTPException

    from app import ecommerce as ecom

    ac, seed = client
    monkeypatch.setattr(ecom, "assert_ecommerce_entitled", lambda tenant: None)
    tenant_id, beta_id = seed["t1"].id, seed["t2"].id
    shopper = m.EcommerceShopper(
        tenant_id=tenant_id, email="shopper@example.com", name="Shopper", password_hash=hash_password(GOOD)
    )
    db_session.add(shopper)
    await db_session.commit()
    sid = shopper.id

    async def attempt(email="shopper@example.com", password=GOOD):
        tenant = await db_session.get(m.Tenant, tenant_id)
        try:
            await ecom.login_shopper(db_session, tenant=tenant, email=email, password=password)
            await db_session.commit()
            return 200, None
        except HTTPException as exc:
            await db_session.rollback()
            return exc.status_code, exc.detail

    for _ in range(5):
        assert (await attempt(password=BAD))[0] == 401
    db_session.expire_all()
    row = await db_session.get(m.EcommerceShopper, sid)
    assert row.locked_until is not None and row.locked_until.tzinfo is not None
    assert round((row.locked_until - row.locked_at).total_seconds() / 60) == 15

    locked = await attempt()
    unknown = await attempt(email="nobody@example.com")
    assert locked == unknown == (401, ecom.SHOPPER_LOGIN_FAILURE)

    # Staff unlock: ecommerce:write, same company only.
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    db_session.add(
        m.User(
            tenant_id=beta_id, email="admin@beta.example.com", full_name="Beta Admin",
            password_hash=hash_password(GOOD), role="company_admin", email_verified=True,
        )
    )
    await db_session.commit()
    beta_admin = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")

    listed = await ac.get("/api/v1/ecommerce/shoppers/sign-in-security", headers=admin)
    assert listed.status_code == 200, listed.text
    assert [r["shopper_id"] for r in listed.json()["data"]] == [sid]
    assert (await ac.post(f"/api/v1/ecommerce/shoppers/{sid}/unlock", headers=cashier)).status_code == 403
    assert (await ac.post(f"/api/v1/ecommerce/shoppers/{sid}/unlock", headers=beta_admin)).status_code == 404
    done = await ac.post(f"/api/v1/ecommerce/shoppers/{sid}/unlock", headers=admin)
    assert done.status_code == 200, done.text
    db_session.expire_all()
    assert (await attempt())[0] == 200


# ---------------------------------------------------------------- timezone-aware lock times


@pytest.mark.asyncio
async def test_lock_times_are_timezone_aware_utc(client, db_session):
    ac, _ = client
    await _fail(ac, 5)
    user = await _user(db_session)
    for value in (user.locked_until, user.locked_at, user.last_failed_login_at):
        assert value.tzinfo is not None and value.utcoffset() == timedelta(0)
    # A naive value written elsewhere is read back as the same instant in UTC.
    naive = datetime(2030, 1, 2, 3, 4, 5)
    user.locked_until = naive
    await db_session.commit()
    user = await _user(db_session)
    assert user.locked_until == naive.replace(tzinfo=timezone.utc)
    assert auth_guard.iso_utc(user.locked_until) == "2030-01-02T03:04:05Z"


# ---------------------------------------------------------------- forwarded headers only from proxies


def test_direct_callers_cannot_choose_their_ip_with_forwarded_for(monkeypatch):
    from app.middleware import client_ip_from_request

    def req(xff, peer):
        return SimpleNamespace(headers={"x-forwarded-for": xff} if xff else {}, client=SimpleNamespace(host=peer))

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "")
    # Reached us directly from the internet: the header is only the caller's own claim.
    assert client_ip_from_request(req("8.8.8.8", "41.66.1.2")) == "41.66.1.2"
    # Through a private proxy hop: the nearest public address it recorded.
    assert client_ip_from_request(req("8.8.8.8, 41.66.1.2", "172.18.0.5")) == "41.66.1.2"

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.0/8")
    # With a proxy list, a peer not on it is believed only about itself.
    assert client_ip_from_request(req("8.8.8.8", "192.168.1.5")) == "192.168.1.5"
    assert client_ip_from_request(req("8.8.8.8, 41.66.1.2", "10.0.3.4")) == "41.66.1.2"


@pytest.mark.asyncio
async def test_uvicorn_proxy_headers_with_docker_ranges(monkeypatch):
    """The production flag: uvicorn resolves the visitor only for proxy peers; the app agrees."""
    from starlette.requests import Request
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    from app.middleware import client_ip_from_request

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "")
    seen: dict = {}

    async def inner(scope, receive, send):
        seen["ip"] = client_ip_from_request(Request(scope))

    proxied = ProxyHeadersMiddleware(inner, trusted_hosts="172.16.0.0/12,10.0.0.0/8,127.0.0.1")

    async def call(peer, xff):
        scope = {
            "type": "http", "method": "GET", "path": "/", "headers": [(b"x-forwarded-for", xff.encode())],
            "client": (peer, 1234), "server": ("x", 80), "scheme": "http", "query_string": b"",
            "root_path": "", "http_version": "1.1",
        }
        await proxied(scope, None, None)
        return seen["ip"]

    # Traefik on the Docker network appended the real visitor; a forged left-hand value is ignored.
    assert await call("10.0.1.7", "6.6.6.6, 41.66.1.2") == "41.66.1.2"
    # A caller outside the proxy ranges cannot pick its address.
    assert await call("41.66.9.9", "6.6.6.6") == "41.66.9.9"


def test_deploy_files_no_longer_trust_every_proxy():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for rel in ("docker-compose.dokploy.yml", "docker-compose.prod.yml", "backend/Dockerfile"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "--forwarded-allow-ips='*'" not in text, rel
        assert "FORWARDED_ALLOW_IPS" in text, rel
