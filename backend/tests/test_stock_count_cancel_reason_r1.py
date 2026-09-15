"""Stock count Cancel reason honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_cancel_reason_ui_wired():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "countCancelReason" in inv
    assert "Required before Cancel" in inv
    assert 'aria-label="Stock count cancel reason"' in inv
    assert "aria-label={`Cancel stock count ${c.id}`}" in inv
    assert "Enter a cancel reason before cancelling a stock count" in inv
    assert "JSON.stringify({ reason })" in inv
    assert "setCountCancelReason" in inv


async def _wh_with_stock(db_session, seed, *, code="CCR"):
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    await db_session.commit()
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name=f"Count Cancel {code}", code=code
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
        quantity_delta=4,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()
    return wh


@pytest.mark.asyncio
async def test_stock_count_cancel_requires_reason_and_persists(client, db_session):
    ac, seed = client
    wh = await _wh_with_stock(db_session, seed, code="CCR1")
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={
            "warehouse_id": wh.id,
            "product_ids": [seed["p1"].id],
            "notes": "original count note",
        },
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]

    missing = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422

    ok = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={"reason": "Count abandoned — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    notes = body.get("notes") or ""
    assert "original count note" in notes
    assert "Cancel: Count abandoned — API hello-world" in notes

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "stock_count_cancelled",
                m.AuditLog.entity_id == cid,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Count abandoned — API hello-world"
