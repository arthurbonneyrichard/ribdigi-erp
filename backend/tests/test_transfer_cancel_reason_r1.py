"""Stock / store transfer Cancel reason honesty (BR-5.2/5.4 / BR-13.2)."""

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


def test_transfer_cancel_reason_ui_wired():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    for page in (inv, stores):
        assert "xferRejectReason" in page
        assert "Enter a cancel reason before cancelling" in page
        assert "action === 'reject' || action === 'cancel'" in page or (
            "action === 'cancel'" in page and "JSON.stringify({ reason:" in page
        )
        assert "Required before Reject or Cancel" in page
        assert "rejection_reason" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _wh_pair(db_session, seed):
    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Cancel From", code="CF1"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Cancel To", code="CT1"
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
    return from_wh, to_wh


@pytest.mark.asyncio
async def test_inventory_stock_transfer_cancel_requires_reason(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    from_wh, to_wh = await _wh_pair(db_session, seed)

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
    if created.json()["data"]["status"] == "draft":
        sub = await ac.post(f"/api/v1/inventory/stock-transfers/{tid}/submit", headers=headers)
        assert sub.status_code == 200, sub.text

    missing = await ac.post(f"/api/v1/inventory/stock-transfers/{tid}/cancel", headers=headers, json={})
    assert missing.status_code == 422, missing.text
    assert "reason" in missing.text.lower()

    blank = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/cancel",
        headers=headers,
        json={"reason": "  "},
    )
    assert blank.status_code == 422, blank.text

    ok = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/cancel",
        headers=headers,
        json={"reason": "Duplicate request — cancel hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert body["rejection_reason"] == "Duplicate request — cancel hello-world"


@pytest.mark.asyncio
async def test_stores_transfer_cancel_requires_reason(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    from_wh, to_wh = await _wh_pair(db_session, seed)

    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=from_wh.id,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": from_wh.store_id,
            "to_store_id": to_wh.store_id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["id"]

    blank = await ac.post(
        f"/api/v1/stores/transfers/{tid}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    assert blank.status_code == 422, blank.text

    whitespace = await ac.post(
        f"/api/v1/stores/transfers/{tid}/cancel",
        headers=headers,
        json={"reason": "   "},
    )
    assert whitespace.status_code == 422, whitespace.text

    ok = await ac.post(
        f"/api/v1/stores/transfers/{tid}/cancel",
        headers=headers,
        json={"reason": "No longer needed — store cancel HW"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert body["rejection_reason"] == "No longer needed — store cancel HW"
