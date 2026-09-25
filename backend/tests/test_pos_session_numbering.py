"""POS shift session year-series numbering (BR-8.2 / BR-20.4). Server-allocated only."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_session_numbering_series(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    year = datetime.utcnow().year

    db_session.add(
        m.PosSession(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            session_number=f"SHIFT-{year}-0010",
            status="closed",
            opening_cash=0,
            expected_cash=0,
            cash_sales=0,
            card_sales=0,
            other_sales=0,
            total_sales=0,
            sale_count=0,
        )
    )
    await db_session.commit()

    blocked = await ac.patch(
        "/api/v1/pos/settings",
        headers=headers,
        json={"pos_session_numbering": {"prefix": "SHIFT", "next_number": 11}},
    )
    assert blocked.status_code == 400, blocked.text

    settings = await ac.get("/api/v1/pos/settings", headers=headers)
    assert settings.status_code == 200, settings.text
    data = settings.json()["data"]
    assert data["pos_session_numbering"]["prefix"] == "SHIFT"
    assert data["pos_session_numbering"]["server_allocated"] is True
    assert data["pos_session_numbering"]["editable"] is False
    assert data["pos_sale_numbering"]["server_allocated"] is True

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=headers,
                json={"actual_cash": 0},
            )

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 40},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["session_number"] == f"SHIFT-{year}-0011"

    nxt = await ac.get("/api/v1/pos/settings", headers=headers)
    assert nxt.status_code == 200
    assert nxt.json()["data"]["pos_session_numbering"]["preview"] == f"SHIFT-{year}-0012"
