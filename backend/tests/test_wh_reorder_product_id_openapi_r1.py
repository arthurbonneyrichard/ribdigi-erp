"""WarehouseReorderPolicyUpdate.product_id ∈ UuidIdValue OpenAPI honesty (BR-5.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue, WarehouseReorderPolicyUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_WH = "11111111-2222-3333-4444-555555555555"


def test_wh_reorder_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = WarehouseReorderPolicyUpdate.model_validate(
        {
            "warehouse_id": _WH,
            "product_id": f"  {_VALID}  ",
            "reorder_level": 1,
            "reorder_qty": 2,
        }
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        with pytest.raises(ValidationError):
            WarehouseReorderPolicyUpdate.model_validate(
                {
                    "warehouse_id": _WH,
                    "product_id": bad,
                    "reorder_level": 1,
                    "reorder_qty": 2,
                }
            )


def test_wh_reorder_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Warehouse reorder product"' in page
    assert "product_id: whReorderProductId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse reorder product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Warehouse reorder product" in docs


@pytest.mark.asyncio
async def test_wh_reorder_product_id_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    from sqlalchemy import select

    from app import models as m
    from app.stores import create_store

    store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        name="Tip398 Wh Store",
        code=f"T398{uuid4().hex[:4]}".upper(),
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

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.put(
            "/api/v1/inventory/warehouse-stock/reorder",
            headers=headers,
            json={
                "warehouse_id": warehouse_id,
                "product_id": bad,
                "reorder_level": 1,
                "reorder_qty": 2,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.put(
        "/api/v1/inventory/warehouse-stock/reorder",
        headers=headers,
        json={
            "warehouse_id": warehouse_id,
            "product_id": f"  {str(uuid4()).upper()}  ",
            "reorder_level": 1,
            "reorder_qty": 2,
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
