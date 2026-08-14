"""Store soft-deactivate — Multi-Store UI + POS/sales inactive guards (BR-2.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_store_soft_deactivate_ui_wired():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "setStoreActive" in stores
    assert "Deactivate" in stores
    assert "Activate" in stores
    assert 'JSON.stringify({ is_active: isActive })' in stores
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "s.is_active !== false" in sales


@pytest.mark.asyncio
async def test_inactive_store_blocked_on_pos_and_sales(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "Deact Store Co", "code": "DEACT-ST", "address": "1 Quiet Rd"},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]
    assert created.json()["data"]["is_active"] is True

    deact = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["is_active"] is False

    pos_list = await ac.get("/api/v1/pos/stores", headers=admin)
    assert pos_list.status_code == 200
    ids = {s["id"] for s in pos_list.json()["data"]}
    assert sid not in ids

    blocked_pos = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"store_id": sid, "opening_cash": 100},
    )
    assert blocked_pos.status_code == 400, blocked_pos.text
    assert "inactive" in blocked_pos.json()["detail"].lower()

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Store Deact Buyer", "kind": "customer", "email": "store-deact@example.com"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]

    blocked_inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cid,
            "store_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert blocked_inv.status_code == 400, blocked_inv.text
    assert "inactive" in blocked_inv.json()["detail"].lower()

    react = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 200
    assert react.json()["data"]["is_active"] is True

    ok_inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cid,
            "store_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert ok_inv.status_code == 200, ok_inv.text
    assert ok_inv.json()["data"]["store_id"] == sid
