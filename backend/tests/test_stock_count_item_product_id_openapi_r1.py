"""StockCountItemUpdate.product_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockCountItemUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_stock_count_item_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = StockCountItemUpdate.model_validate(
        {"product_id": f"  {_VALID}  ", "counted_qty": 1}
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "p1"):
        with pytest.raises(ValidationError):
            StockCountItemUpdate.model_validate(
                {"product_id": bad, "counted_qty": 1}
            )


def test_stock_count_item_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "product_id: String(item.product_id).trim()" in page
    assert 'aria-label="Save count lines"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count item product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "product_id" in docs
    assert "stock-counts" in docs


@pytest.mark.asyncio
async def test_stock_count_item_product_id_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    from sqlalchemy import select

    from app import models as m
    from app.stores import create_store

    store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        name="Tip400 Count Store",
        code=f"T400{uuid4().hex[:4]}".upper(),
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
    product_id = seed["p1"].id

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": warehouse_id, "product_ids": [product_id]},
    )
    assert created.status_code == 200, created.text
    count_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "p1"):
        resp = await ac.patch(
            f"/api/v1/inventory/stock-counts/{count_id}/items",
            headers=headers,
            json={"items": [{"product_id": bad, "counted_qty": 1}]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count_id}/items",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": f"  {str(uuid4()).upper()}  ",
                    "counted_qty": 1,
                }
            ]
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
