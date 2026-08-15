"""Stock count Cancel UI + API (BR-5.2) — abandon draft without posting variances."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_cancel_ui_wired():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "/inventory/stock-counts/${id}/cancel" in inv
    assert "Cancel count" in inv
    assert "cancelStockCount" in inv
    assert "countCancelReason" in inv
    assert "Required before Cancel" in inv


@pytest.mark.asyncio
async def test_cancel_draft_stock_count_and_block_completed(client, db_session):
    ac, seed = client
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    await db_session.commit()

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Cancel Count Store", code="CCS"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
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
        warehouse_id=wh.id,
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh.id, "product_ids": [seed["p1"].id]},
    )
    assert created.status_code == 200, created.text
    count = created.json()["data"]
    assert count["status"] == "draft"
    assert count.get("can_cancel") is True
    cid = count["id"]
    before_qty = float((await db_session.get(m.Product, seed["p1"].id)).stock_qty)

    cancelled = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={"reason": "Wrong warehouse — draft cancel"},
    )
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()["data"]
    assert body["status"] == "cancelled"
    assert body.get("can_cancel") is False
    assert "Cancel: Wrong warehouse — draft cancel" in (body.get("notes") or "")

    again = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={"reason": "retry"},
    )
    assert again.status_code == 409, again.text

    product = await db_session.get(m.Product, seed["p1"].id)
    await db_session.refresh(product)
    assert float(product.stock_qty) == before_qty  # cancel must not post variances

    # Completed counts cannot cancel
    created2 = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh.id, "product_ids": [seed["p1"].id]},
    )
    assert created2.status_code == 200, created2.text
    cid2 = created2.json()["data"]["id"]
    patched = await ac.patch(
        f"/api/v1/inventory/stock-counts/{cid2}/items",
        headers=headers,
        json={"items": [{"product_id": seed["p1"].id, "counted_qty": 5}]},
    )
    assert patched.status_code == 200, patched.text
    done = await ac.post(f"/api/v1/inventory/stock-counts/{cid2}/complete", headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["data"].get("can_cancel") is False
    blocked = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid2}/cancel",
        headers=headers,
        json={"reason": "should fail after complete"},
    )
    assert blocked.status_code == 409, blocked.text
