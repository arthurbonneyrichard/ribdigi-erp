"""Stage 167 E1 — Hold soft-reserve expiry / cleanup."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_hold_sets_expires_at_when_reserved_e1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    product.stock_qty = 25
    product.reserved_qty = 0
    await db_session.commit()

    held = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "TTL hold",
            "reserve_stock": True,
            "cart_payload": {
                "items": [{"product_id": product.id, "quantity": 2}],
            },
        },
    )
    assert held.status_code == 200, held.text
    data = held.json()["data"]
    assert data["stock_reserved"] is True
    assert data["expires_at"]
    assert data.get("reserve_ttl_hours") == 4


@pytest.mark.asyncio
async def test_pos_hold_expire_stale_releases_reserve_e1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    product.stock_qty = 25
    product.reserved_qty = 0
    await db_session.commit()

    held = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "Expire me",
            "reserve_stock": True,
            "cart_payload": {
                "items": [{"product_id": product.id, "quantity": 4}],
            },
        },
    )
    assert held.status_code == 200, held.text
    hold_id = held.json()["data"]["id"]

    await db_session.refresh(product)
    assert float(product.reserved_qty or 0) == 4.0

    row = await db_session.get(m.PosHeldCart, hold_id)
    assert row is not None
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    expired = await ac.post("/api/v1/pos/holds/expire-stale", headers=headers, json={})
    assert expired.status_code == 200, expired.text
    body = expired.json()["data"]
    assert body["expired_count"] >= 1
    assert any(h["id"] == hold_id for h in body["holds"])

    await db_session.refresh(product)
    assert float(product.reserved_qty or 0) == 0.0

    listed = await ac.get("/api/v1/pos/holds?status=held", headers=headers)
    assert listed.status_code == 200, listed.text
    assert not any(r["id"] == hold_id for r in listed.json()["data"])

    resume = await ac.post(
        f"/api/v1/pos/holds/{hold_id}/resume", headers=headers, json={}
    )
    assert resume.status_code == 409, resume.text


def test_hold_expiry_migration_and_ui_e1():
    mig = (
        ROOT / "backend/alembic/versions/20260813_0095_pos_held_cart_expires_at.py"
    ).read_text(encoding="utf-8")
    assert "expires_at" in mig
    models = (ROOT / "backend/app/models.py").read_text(encoding="utf-8")
    assert "expires_at" in models
    holds = (ROOT / "backend/app/pos_holds.py").read_text(encoding="utf-8")
    assert "HOLD_SOFT_RESERVE_TTL_HOURS" in holds
    assert "expire_stale_holds" in holds
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "/pos/holds/expire-stale" in api
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "Expire stale soft-reserves" in pos
    assert "expires_at" in pos
