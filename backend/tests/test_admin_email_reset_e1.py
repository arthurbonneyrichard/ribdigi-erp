"""Stage 85 E1 — Tenant Admin email-initiated password reset."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_admin_email_password_reset_issues_token(client, db_engine):
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        cash = (
            await db.execute(
                select(m.User).where(m.User.email == "cashier@alpha.example.com")
            )
        ).scalar_one()
        user_id = cash.id

    r = await ac.post(f"/api/v1/users/{user_id}/password-reset-email", headers=admin, json={})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["email"] == "cashier@alpha.example.com"
    assert "email_delivery" in data
    assert data.get("reset_token")

    async with session_factory() as db:
        tok = (
            await db.execute(
                select(m.AuthToken).where(
                    m.AuthToken.user_id == user_id,
                    m.AuthToken.purpose == "password_reset",
                )
            )
        ).scalars().first()
        assert tok is not None


@pytest.mark.asyncio
async def test_admin_email_reset_requires_users_write(client):
    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/users/does-not-matter/password-reset-email",
        headers=cash,
        json={},
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_admin_email_reset_foreign_user_404(client, db_engine):
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        other = (
            await db.execute(select(m.User).where(m.User.email == "cashier@beta.example.com"))
        ).scalar_one()
        foreign_id = other.id
    r = await ac.post(f"/api/v1/users/{foreign_id}/password-reset-email", headers=admin, json={})
    assert r.status_code == 404


def test_users_ui_has_email_reset_action():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "password-reset-email" in page
    assert "Email reset link" in page
