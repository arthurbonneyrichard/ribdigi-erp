"""POS sale year-series numbering (BR-8.1 / BR-20.4). Server-allocated only."""

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


async def _close_open_shift(ac, headers, admin_headers):
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=admin_headers,
                json={"actual_cash": 0},
            )


@pytest.mark.asyncio
async def test_pos_sale_numbering_series(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    year = datetime.utcnow().year
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 25

    db_session.add(
        m.Transaction(
            tenant_id=seed["t1"].id,
            tx_type="pos_sale",
            reference=f"POS-{year}-0041",
            subtotal=1,
            tax=0,
            total=1,
            status="completed",
            payload={},
            client_request_id="seed-pos-num-0041xx",
        )
    )
    await db_session.commit()

    blocked = await ac.patch(
        "/api/v1/pos/settings",
        headers=headers,
        json={"pos_sale_numbering": {"prefix": "HACK", "next_number": 1}},
    )
    assert blocked.status_code == 400, blocked.text

    settings = await ac.get("/api/v1/pos/settings", headers=headers)
    assert settings.status_code == 200, settings.text
    sale_cfg = settings.json()["data"]["pos_sale_numbering"]
    assert sale_cfg["prefix"] == "POS"
    assert sale_cfg["server_allocated"] is True
    assert sale_cfg["editable"] is False
    assert sale_cfg["year"] == year
    assert sale_cfg["pattern"] == "POS-{YYYY}-{NNNN}"

    await _close_open_shift(ac, headers, headers)

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 25}],
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["data"]["reference"] == f"POS-{year}-0042"

    nxt = await ac.get("/api/v1/pos/settings", headers=headers)
    assert nxt.status_code == 200
    assert nxt.json()["data"]["pos_sale_numbering"]["preview"] == f"POS-{year}-0043"
