"""POS sale client_request_id idempotency (offline sync)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_sale_client_request_id_idempotent(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            # Cashier may lack close — use admin if needed
            admin = await _admin(ac, seed)
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=admin,
                json={"actual_cash": 0},
            )

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 0},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]

    body = {
        "session_id": session_id,
        "client_request_id": "cr-test-idempotent-001",
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
    }
    first = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    sale_id = first.json()["data"]["id"]
    ref = first.json()["data"]["reference"]
    assert first.json()["data"].get("idempotent_replay") is not True

    second = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == sale_id
    assert second.json()["data"]["reference"] == ref
    assert second.json()["data"].get("idempotent_replay") is True
