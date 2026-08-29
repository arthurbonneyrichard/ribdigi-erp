"""StockMove.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockMove, UuidIdValue
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_stock_move_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = StockMove.model_validate({"product_id": _PRODUCT, "quantity": 1})
    assert omit.warehouse_id is None
    ok = StockMove.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "warehouse_id": f"  {_VALID}  "}
    )
    assert ok.warehouse_id == _VALID.lower()
    nullish = StockMove.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "warehouse_id": None}
    )
    assert nullish.warehouse_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            StockMove.model_validate(
                {"product_id": _PRODUCT, "quantity": 1, "warehouse_id": bad}
            )


def test_stock_move_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in warehouse"' in page
    assert "warehouse_id: stockWarehouseId.trim() || null" in page
    assert 'aria-label="Receive batch"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "StockMove warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /inventory/stock-in" in docs
    assert "Stock-in warehouse" in docs


@pytest.mark.asyncio
async def test_stock_move_warehouse_id_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": product_id, "quantity": 1, "warehouse_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        name="Tip293 Stock WH Store",
        code="T293",
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
    await db_session.commit()
    warehouse_id = wh.id

    ok = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "warehouse_id": f"  {str(warehouse_id).upper()}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    got_wh = (
        data.get("warehouse_id")
        or (data.get("batch") or {}).get("warehouse_id")
        or (data.get("movement") or {}).get("warehouse_id")
    )
    if got_wh is not None:
        assert str(got_wh).lower() == str(warehouse_id).lower()

    missing = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "warehouse_id": str(uuid4()),
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
