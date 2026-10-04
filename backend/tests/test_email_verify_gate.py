"""Email verification required before login (BR-19.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import emailer
from app import models as m
from app.security import hash_password, issue_one_time_token


@pytest.mark.asyncio
async def test_login_blocked_until_email_verified(client, db_session, seeded):
    ac, seed = client
    emailer.clear_dev_outbox()
    user = m.User(
        tenant_id=seed["t1"].id,
        email="unverified@alpha.example.com",
        full_name="Unverified User",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=False,
        is_active=True,
        permissions={},
    )
    db_session.add(user)
    await db_session.commit()

    blocked = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "unverified@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert blocked.status_code == 403, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "EMAIL_NOT_VERIFIED"
    assert "access_token" not in (blocked.json().get("data") or {})

    # Resend issues token (non-prod)
    resend = await ac.post(
        "/api/v1/auth/resend-verification",
        json={"email": "unverified@alpha.example.com", "tenant_id": "alpha"},
    )
    assert resend.status_code == 200, resend.text
    token = resend.json()["data"].get("verification_token")
    assert token
    assert emailer.get_dev_outbox()

    verified = await ac.post(
        "/api/v1/auth/verify-email",
        json={"token": token},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["verified"] is True

    await db_session.refresh(user)
    assert user.email_verified is True

    ok = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "unverified@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_resend_verification_neutral_for_unknown(client):
    ac, _seed = client
    r = await ac.post(
        "/api/v1/auth/resend-verification",
        json={"email": "ghost@example.com", "tenant_id": "alpha"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["requested"] is True
    assert "verification_token" not in r.json()["data"]


@pytest.mark.asyncio
async def test_resend_invalidates_prior_unused_token(client, db_session, seeded):
    ac, seed = client
    user = m.User(
        tenant_id=seed["t1"].id,
        email="resend-prior@alpha.example.com",
        full_name="Resend Prior",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=False,
        is_active=True,
        permissions={},
    )
    db_session.add(user)
    await db_session.flush()
    raw1, hash1, exp1 = issue_one_time_token()
    db_session.add(
        m.AuthToken(
            tenant_id=seed["t1"].id,
            user_id=user.id,
            purpose="email_verify",
            token_hash=hash1,
            expires_at=exp1,
        )
    )
    await db_session.commit()

    resend = await ac.post(
        "/api/v1/auth/resend-verification",
        json={"email": "resend-prior@alpha.example.com", "tenant_id": "alpha"},
    )
    assert resend.status_code == 200
    new_token = resend.json()["data"]["verification_token"]
    assert new_token != raw1

    # Old token no longer works
    old = await ac.post("/api/v1/auth/verify-email", json={"token": raw1})
    assert old.status_code == 400

    ok = await ac.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert ok.status_code == 200

    rows = (
        await db_session.execute(
            select(m.AuthToken).where(
                m.AuthToken.user_id == user.id,
                m.AuthToken.purpose == "email_verify",
            )
        )
    ).scalars().all()
    assert all(r.used_at is not None for r in rows)
