"""Stock transfer Reject reason honesty (BR-5.2/5.4) — FE sends real reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_transfer_reject_reason_ui_wired():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "xferRejectReason" in inv
    assert "Enter a reject reason before rejecting a stock transfer" in inv
    assert "JSON.stringify({ reason: xferRejectReason.trim() })" in inv
    assert "rejection_reason" in inv
    assert 'aria-label="Stock transfer reject reason"' in inv


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_inventory_stock_transfer_reject_persists_reason(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Xfer From", code="XF1"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Xfer To", code="XT1"
    )
    await db_session.flush()
    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    to_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == to_store.id,
            )
        )
    ).scalar_one()

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=from_wh.id,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": from_wh.id,
            "to_warehouse_id": to_wh.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] in {"requested", "draft"}

    # Ensure requested
    if created.json()["data"]["status"] == "draft":
        sub = await ac.post(f"/api/v1/inventory/stock-transfers/{tid}/submit", headers=headers)
        assert sub.status_code == 200, sub.text

    rejected = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/reject",
        headers=headers,
        json={"reason": "Wrong destination warehouse"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()["data"]
    assert body["status"] == "cancelled"
    assert body["rejection_reason"] == "Wrong destination warehouse"
