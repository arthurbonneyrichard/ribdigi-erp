"""WarehouseReorderPolicyUpdate.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-5.4)."""

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
_PROD = "11111111-2222-3333-4444-555555555555"


def test_wh_reorder_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = WarehouseReorderPolicyUpdate.model_validate(
        {
            "warehouse_id": f"  {_VALID}  ",
            "product_id": _PROD,
            "reorder_level": 1,
            "reorder_qty": 2,
        }
    )
    assert ok.warehouse_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        with pytest.raises(ValidationError):
            WarehouseReorderPolicyUpdate.model_validate(
                {
                    "warehouse_id": bad,
                    "product_id": _PROD,
                    "reorder_level": 1,
                    "reorder_qty": 2,
                }
            )


def test_wh_reorder_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Warehouse stock warehouse"' in page
    assert "warehouse_id: whStockWarehouseId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse reorder warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Warehouse stock warehouse" in docs
    assert "warehouse-stock/reorder" in docs


@pytest.mark.asyncio
async def test_wh_reorder_warehouse_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.put(
            "/api/v1/inventory/warehouse-stock/reorder",
            headers=headers,
            json={
                "warehouse_id": bad,
                "product_id": product_id,
                "reorder_level": 1,
                "reorder_qty": 2,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.put(
        "/api/v1/inventory/warehouse-stock/reorder",
        headers=headers,
        json={
            "warehouse_id": f"  {str(uuid4()).upper()}  ",
            "product_id": product_id,
            "reorder_level": 1,
            "reorder_qty": 2,
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
