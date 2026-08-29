"""StockTransferCreate.to_store_id ∈ UuidIdValue OpenAPI honesty (BR-5.2 / BR-13.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockTransferCreate, UuidIdValue
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID_FROM = "11111111-2222-3333-4444-555555555555"
_VALID_TO = "22222222-3333-4444-5555-666666666666"
_VALID_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_ITEMS = [{"product_id": _VALID_PRODUCT, "quantity": 1}]


def test_stock_transfer_to_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID_TO}  ") == _VALID_TO.lower()
    ok = StockTransferCreate.model_validate(
        {
            "from_store_id": _VALID_FROM,
            "to_store_id": f"  {_VALID_TO}  ",
            "items": _ITEMS,
        }
    )
    assert ok.to_store_id == _VALID_TO.lower()
    omit_ok = StockTransferCreate.model_validate(
        {
            "from_warehouse_id": _VALID_FROM,
            "to_warehouse_id": _VALID_TO,
            "items": _ITEMS,
        }
    )
    assert omit_ok.to_store_id is None
    nullish = StockTransferCreate.model_validate(
        {
            "to_store_id": None,
            "from_warehouse_id": _VALID_FROM,
            "to_warehouse_id": _VALID_TO,
            "items": _ITEMS,
        }
    )
    assert nullish.to_store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "st_002", "a b"):
        with pytest.raises(ValidationError):
            StockTransferCreate.model_validate(
                {
                    "from_store_id": _VALID_FROM,
                    "to_store_id": bad,
                    "items": _ITEMS,
                }
            )


def test_stock_transfer_to_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock transfer to store"' in page
    assert "to_store_id: toStore.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock transfer to_store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stock transfer to store" in docs
    assert "POST /stores/transfers" in docs


@pytest.mark.asyncio
async def test_stock_transfer_to_store_id_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    from_store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        name=f"Tip345 From {suffix}",
        code=f"F345{suffix[:4]}".upper(),
    )
    await db_session.commit()

    products = await ac.get("/api/v1/products", headers=headers)
    assert products.status_code == 200, products.text
    product_rows = products.json().get("data") or []
    assert len(product_rows) >= 1, products.text
    product_id = product_rows[0]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "st_002"):
        resp = await ac.post(
            "/api/v1/stores/transfers",
            headers=headers,
            json={
                "from_store_id": from_store.id,
                "to_store_id": bad,
                "submit": False,
                "items": [{"product_id": product_id, "quantity": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": from_store.id,
            "to_store_id": f"  {str(uuid4()).upper()}  ",
            "submit": False,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
