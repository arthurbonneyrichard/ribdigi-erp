"""Stage 12 A1: POS domain audit for session open/close and completed sales."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_session_and_sale_audited(client, db_session):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    seed["p1"].selling_price = 50
    seed["p1"].stock_qty = 20
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]

    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=cashier,
        json={"actual_cash": 100},
    )
    assert closed.status_code == 200, closed.text

    headers = await _super_headers(ac, seed)
    for action, entity_id in (
        ("pos_session_opened", session_id),
        ("pos_sale_completed", sale_id),
        ("pos_session_closed", session_id),
    ):
        listed = await ac.get(
            "/api/v1/audit-logs",
            headers=headers,
            params={"action": action},
        )
        assert listed.status_code == 200, listed.text
        row = next(r for r in listed.json()["data"] if r["entity_id"] == entity_id)
        assert row["integrity_hash"]
        assert row["module"] == "pos"

    # Sales-side payment audit already exists; assert OTC invoice_posted still present in suite seed
    verify = await ac.get("/api/v1/audit-logs/verify", headers=headers)
    assert verify.status_code == 200
    assert verify.json()["data"]["valid"] is True
