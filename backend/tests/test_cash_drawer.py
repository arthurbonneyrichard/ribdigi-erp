"""Cash drawer hardware abstraction and POS integration."""

from __future__ import annotations

from unittest.mock import patch

import pyotp
import pytest

from app.cash_drawer import kick_base64, kick_bytes, normalize_mode
from tests.conftest import auth_headers


def test_kick_bytes_are_escpos_pulse():
    assert kick_bytes() == bytes([0x1B, 0x70, 0x00, 0x19, 0xFA])
    assert kick_base64()


def test_normalize_mode():
    assert normalize_mode("Mock") == "mock"
    with pytest.raises(Exception):
        normalize_mode("usb")


async def _cashier_headers(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin_headers(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_manual_drawer_open_requires_specific_reason(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "mock")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "mock")

    ac, seeded = client
    headers = await _cashier_headers(ac)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    blank = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "  "},
    )
    assert blank.status_code == 422, blank.text

    placeholder = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "manual"},
    )
    assert placeholder.status_code == 422, placeholder.text

    ok = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "Customer change request"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["ok"] is True
    assert ok.json()["data"]["reason"] == "Customer change request"


@pytest.mark.asyncio
async def test_manual_drawer_open_mock_fallback(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "mock")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "mock")

    ac, seeded = client
    headers = await _cashier_headers(ac)

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    kick = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "no_sale"},
    )
    assert kick.status_code == 200, kick.text
    body = kick.json()["data"]
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["kick_base64"] == kick_base64()
    assert body["reason"] == "no_sale"

    summary = await ac.get(f"/api/v1/pos/sessions/{session_id}/drawer", headers=headers)
    assert summary.status_code == 200
    assert "hardware" in summary.json()["data"]
    assert "expected_cash" in summary.json()["data"]


@pytest.mark.asyncio
async def test_store_drawer_settings_and_cash_sale_pulse(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "none")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "none")

    ac, seeded = client
    admin = await _admin_headers(ac, seeded)
    cashier = await _cashier_headers(ac)

    store = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "POS1", "name": "POS Store"},
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={
            "drawer_mode": "mock",
            "drawer_open_on_cash": True,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["drawer_mode"] == "mock"

    # Seed a product for sale
    product = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "Drawer Widget",
            "sku": "DRW-1",
            "cost_price": 1,
            "selling_price": 5,
            "stock_qty": 20,
        },
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 10, "store_id": store_id},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "status": "completed",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    assert data["drawer"]["ok"] is True
    assert data["drawer"]["mode"] == "mock"

    card = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "card",
            "status": "completed",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert card.status_code == 200, card.text
    assert "drawer" not in card.json()["data"] or card.json()["data"].get("drawer") is None


@pytest.mark.asyncio
async def test_network_drawer_sends_socket(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "none")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "none")

    ac, seeded = client
    admin = await _admin_headers(ac, seeded)
    cashier = await _cashier_headers(ac)

    store = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "NET1", "name": "Network Drawer Store"},
    )
    store_id = store.json()["data"]["id"]
    await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={"drawer_mode": "network", "drawer_host": "127.0.0.1", "drawer_port": 9100},
    )

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0, "store_id": store_id},
    )
    session_id = opened.json()["data"]["session_id"]

    with patch("app.cash_drawer._send_network") as send:
        r = await ac.post(
            f"/api/v1/pos/sessions/{session_id}/drawer/open",
            headers=cashier,
            json={"reason": "network pulse check"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["ok"] is True
    assert r.json()["data"]["reason"] == "network pulse check"
    send.assert_called_once()
    args = send.call_args[0]
    assert args[0] == "127.0.0.1"
    assert args[1] == 9100
    assert args[2] == kick_bytes()
