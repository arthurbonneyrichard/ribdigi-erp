"""StockTransferReject.reason OpenAPI honesty (BR-5.2/5.4 / BR-13.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.schemas import StockTransferReject
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_transfer_reject_reason_schema():
    ok = StockTransferReject.model_validate({"reason": "  Wrong destination  "})
    assert ok.reason == "Wrong destination"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockTransferReject.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        StockTransferReject.model_validate({})


def test_stock_transfer_reject_reason_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock transfer reject reason"' in inv
    assert 'aria-label="Stock transfer reject reason"' in stores
    assert "xferRejectReason" in inv
    assert "aria-label={`Reject stock transfer ${t.id}`}" in inv
    assert "aria-label={`Reject stock transfer ${t.id}`}" in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "StockTransferRejectReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockTransferRejectReasonValue" in docs


@pytest.mark.asyncio
async def test_stock_transfer_reject_reason_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP194 reject {suffix}"

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name=f"TIP194 From {suffix}", code=f"F{suffix[:6]}"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name=f"TIP194 To {suffix}", code=f"T{suffix[:6]}"
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
    if created.json()["data"]["status"] == "draft":
        sub = await ac.post(f"/api/v1/inventory/stock-transfers/{tid}/submit", headers=headers)
        assert sub.status_code == 200, sub.text

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/inventory/stock-transfers/{tid}/reject",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/inventory/stock-transfers/{tid}/reject",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert body["rejection_reason"] == tag
