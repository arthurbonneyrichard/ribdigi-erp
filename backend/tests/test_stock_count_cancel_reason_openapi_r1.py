"""StockCountCancel.reason OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.schemas import StockCountCancel
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_cancel_reason_schema():
    ok = StockCountCancel.model_validate({"reason": "  Count abandoned mid-session  "})
    assert ok.reason == "Count abandoned mid-session"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockCountCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        StockCountCancel.model_validate({})


def test_stock_count_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock count cancel reason"' in page
    assert "countCancelReason" in page
    assert "aria-label={`Cancel stock count ${c.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "StockCountCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockCountCancelReasonValue" in docs
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "StockCountCancelReasonValue" in brd


async def _wh_with_stock(db_session, seed, *, code="SCO"):
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 0
    await db_session.commit()
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name=f"Count OpenAPI {code}", code=code
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
async def test_stock_count_cancel_reason_api_blank_invalid_422(client, db_session):
    ac, seed = client
    wh = await _wh_with_stock(db_session, seed, code="SCO1")
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={
            "warehouse_id": wh.id,
            "product_ids": [seed["p1"].id],
            "notes": "tip205 draft",
        },
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/inventory/stock-counts/{cid}/cancel",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/inventory/stock-counts/{cid}/cancel",
        headers=headers,
        json={"reason": "Tip205 count abandoned — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert "Cancel: Tip205 count abandoned — API hello-world" in (body.get("notes") or "")
