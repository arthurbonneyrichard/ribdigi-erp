"""A refresh token that was already rotated, coming back later, ends every session of that user."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app.security import hash_token


async def _login(ac, seed):
    body = {
        "email": "super@alpha.example.com",
        "password": "SecurePass123!",
        "tenant_id": "alpha",
        "totp_code": pyotp.TOTP(seed["super_totp_secret"]).now(),
    }
    r = await ac.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_quick_double_refresh_only_refuses(client):
    ac, seed = client
    login = await _login(ac, seed)
    other = await _login(ac, seed)
    first = await ac.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert first.status_code == 200, first.text
    again = await ac.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert again.status_code == 401
    # Two tabs refreshing at once must not log the user out everywhere.
    still = await ac.post("/api/v1/auth/refresh", json={"refresh_token": other["refresh_token"]})
    assert still.status_code == 200, still.text


@pytest.mark.asyncio
async def test_late_reuse_revokes_all_sessions(client, db_engine):
    ac, seed = client
    login = await _login(ac, seed)
    other = await _login(ac, seed)
    rotated = await ac.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert rotated.status_code == 200, rotated.text
    new_refresh = rotated.json()["data"]["refresh_token"]

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        await db.execute(
            update(m.AuthSession)
            .where(m.AuthSession.refresh_token_hash == hash_token(login["refresh_token"]))
            .values(revoked_at=datetime.utcnow() - timedelta(minutes=5))
        )
        await db.commit()

    reuse = await ac.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert reuse.status_code == 401
    for token in (new_refresh, other["refresh_token"]):
        r = await ac.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 401, "every session of the user must be revoked"

    async with factory() as db:
        logged = (
            await db.execute(select(m.AuditLog).where(m.AuditLog.action == "refresh_token_reuse"))
        ).scalars().all()
    assert logged
