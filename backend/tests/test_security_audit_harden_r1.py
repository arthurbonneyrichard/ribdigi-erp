"""In-repo security hardenings from the 25 Oct 2026 audit. No exploit steps."""

from __future__ import annotations

import pyotp
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app import models as m
from app.rbac import can_assign_company_admin
from app.schemas import WebhookCreate
from app.user_import import ASSIGNABLE_ROLES
from tests.conftest import auth_headers
from tests.test_ecommerce_r1 import _seed_storefront


def test_import_roles_exclude_platform_and_company_admin_gate():
    assert "platform_owner" not in ASSIGNABLE_ROLES
    assert "platform_admin" not in ASSIGNABLE_ROLES
    assert "super_admin" not in ASSIGNABLE_ROLES
    assert "cashier" in ASSIGNABLE_ROLES
    assert can_assign_company_admin("company_admin") is True
    assert can_assign_company_admin("store_manager") is False
    assert can_assign_company_admin("cashier") is False


def test_private_https_webhook_url_rejected():
    with pytest.raises(ValidationError):
        WebhookCreate.model_validate(
            {"url": "https://10.0.0.1/hooks", "events": ["webhook.test"]}
        )


@pytest.mark.asyncio
async def test_users_write_cannot_mint_company_admin(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    created = await ac.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "key": "people_desk",
            "label": "People Desk",
            "permissions": {"users": ["read", "write"], "dashboard": ["read"]},
        },
    )
    assert created.status_code == 200, created.text
    user = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "peopledesk@alpha.example.com",
            "full_name": "People Desk",
            "password": "SecurePass123!",
            "role": "people_desk",
        },
    )
    assert user.status_code == 200, user.text
    clerk = await auth_headers(
        ac, email="peopledesk@alpha.example.com", tenant_slug="alpha"
    )
    minted = await ac.post(
        "/api/v1/users",
        headers=clerk,
        json={
            "email": "promoted@alpha.example.com",
            "full_name": "Promoted Admin",
            "password": "SecurePass123!",
            "role": "company_admin",
        },
    )
    assert minted.status_code == 403, minted.text


@pytest.mark.asyncio
async def test_role_change_revokes_existing_sessions(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "demote.me@alpha.example.com",
            "full_name": "Demote Me",
            "password": "SecurePass123!",
            "role": "store_manager",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["data"]["id"]
    victim = await auth_headers(
        ac, email="demote.me@alpha.example.com", tenant_slug="alpha"
    )
    before = await ac.get("/api/v1/me", headers=victim)
    assert before.status_code == 200, before.text
    patched = await ac.patch(
        f"/api/v1/users/{user_id}",
        headers=admin,
        json={"role": "cashier"},
    )
    assert patched.status_code == 200, patched.text
    after = await ac.get("/api/v1/me", headers=victim)
    assert after.status_code == 401, after.text


@pytest.mark.asyncio
async def test_password_reset_replaces_prior_unused_token(client):
    ac, _seed = client
    first = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "mgr@alpha.example.com", "tenant_id": "alpha"},
    )
    assert first.status_code == 200, first.text
    old = first.json()["data"].get("reset_token")
    assert old
    second = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "mgr@alpha.example.com", "tenant_id": "alpha"},
    )
    assert second.status_code == 200, second.text
    new = second.json()["data"].get("reset_token")
    assert new and new != old
    stale = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": old, "new_password": "AnotherSecure99!"},
    )
    assert stale.status_code == 400, stale.text


@pytest.mark.asyncio
async def test_unauthenticated_write_does_not_use_client_tenant_header(
    client, db_session, seeded
):
    ac, seed = client
    before_foreign = (
        await db_session.execute(
            select(func.count())
            .select_from(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == seed["t2"].id,
                m.AuditLog.action == "http_write",
            )
        )
    ).scalar_one()
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=4)
    created = await ac.post(
        f"/api/v1/storefront/cart?preview_token={storefront.preview_token}",
        headers={"X-Tenant-ID": seed["t2"].id},
    )
    assert created.status_code == 200, created.text
    after_foreign = (
        await db_session.execute(
            select(func.count())
            .select_from(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == seed["t2"].id,
                m.AuditLog.action == "http_write",
            )
        )
    ).scalar_one()
    assert after_foreign == before_foreign


@pytest.mark.asyncio
async def test_shopper_history_does_not_attach_guest_orders(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=4)
    preview = storefront.preview_token
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 1},
    )
    guest = await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        json={
            "cart_token": token,
            "guest_name": "Ama Guest",
            "guest_email": "guest.later@example.com",
            "fulfillment": "pickup",
        },
    )
    assert guest.status_code == 200, guest.text
    registered = await ac.post(
        f"/api/v1/storefront/account/register?preview_token={preview}",
        json={
            "name": "Ama Later",
            "email": "guest.later@example.com",
            "password": "Shopper1!",
        },
    )
    assert registered.status_code == 200, registered.text
    session = registered.json()["data"]["session_token"]
    history = await ac.get(
        f"/api/v1/storefront/account/orders?preview_token={preview}",
        headers={"X-Storefront-Shopper": session},
    )
    assert history.status_code == 200, history.text
    assert history.json()["data"]["orders"] == []


@pytest.mark.asyncio
async def test_2fa_challenge_is_single_use_after_success(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.LOGIN_2FA_ENABLED", True)
    ac, seed = client
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "super@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert login.status_code == 200, login.text
    challenge = login.json()["data"]["challenge_token"]
    assert challenge
    bad = await ac.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": challenge, "code": "000000"},
    )
    assert bad.status_code == 401, bad.text
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    ok = await ac.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": challenge, "code": code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("access_token")
    reuse = await ac.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_token": challenge, "code": code},
    )
    assert reuse.status_code == 401, reuse.text


def test_preview_token_compare_accepts_hash_or_plain():
    from app.ecommerce import preview_token_digest, preview_tokens_match

    raw = "preview-plain-token-value"
    assert preview_tokens_match(raw, raw) is True
    assert preview_tokens_match(preview_token_digest(raw), raw) is True
    assert preview_tokens_match(raw, "other-token-value-xx") is False


def test_forwarded_host_default_matches_current_deploy(monkeypatch):
    from app.ecommerce import host_from_request

    monkeypatch.setattr("app.config.settings.TRUST_X_FORWARDED_HOST", True)
    monkeypatch.setattr("app.config.settings.TRUSTED_PROXY_IPS", "")
    assert (
        host_from_request(host="backend:8000", forwarded_host="shop.example.com")
        == "shop.example.com"
    )
    monkeypatch.setattr("app.config.settings.TRUST_X_FORWARDED_HOST", False)
    assert (
        host_from_request(host="backend:8000", forwarded_host="shop.example.com")
        == "backend"
    )


def test_rate_limit_ip_uses_rightmost_or_trusted_walk(monkeypatch):
    from types import SimpleNamespace

    from app.middleware import client_ip_from_request

    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.1.1.1, 2.2.2.2"},
        client=SimpleNamespace(host="10.0.0.2"),
    )
    assert client_ip_from_request(req) == "2.2.2.2"
    monkeypatch.setattr("app.config.settings.TRUSTED_PROXY_IPS", "10.0.0.2")
    behind = SimpleNamespace(
        headers={"x-forwarded-for": "9.9.9.9, 10.0.0.2"},
        client=SimpleNamespace(host="10.0.0.2"),
    )
    assert client_ip_from_request(behind) == "9.9.9.9"
