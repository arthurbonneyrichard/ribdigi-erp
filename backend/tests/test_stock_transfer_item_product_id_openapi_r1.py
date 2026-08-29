"""StockTransferItemCreate.product_id ∈ UuidIdValue OpenAPI honesty (BR-5.2 / BR-13.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockTransferCreate, StockTransferItemCreate, UuidIdValue
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_stock_transfer_item_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = StockTransferItemCreate.model_validate(
        {"product_id": f"  {_VALID}  ", "quantity": 1}
    )
    assert ok.product_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "prod_001", "a b"):
        with pytest.raises(ValidationError):
            StockTransferItemCreate.model_validate({"product_id": bad, "quantity": 1})
    with pytest.raises(ValidationError):
        StockTransferItemCreate.model_validate({"quantity": 1})

    base = {
        "from_warehouse_id": "11111111-2222-3333-4444-555555555555",
        "to_warehouse_id": "22222222-3333-4444-5555-666666666666",
        "items": [{"product_id": _VALID, "quantity": 1}],
    }
    wrapped = StockTransferCreate.model_validate(base)
    assert wrapped.items[0].product_id == _VALID.lower()
    with pytest.raises(ValidationError):
        StockTransferCreate.model_validate(
            {
                **base,
                "items": [{"product_id": "prod_001", "quantity": 1}],
            }
        )


def test_stock_transfer_item_product_id_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Selected product"' in inv
    assert "product_id: selectedId.trim()" in inv
    assert 'aria-label="Create stock transfer"' in inv
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock transfer product"' in stores
    assert "product_id: productId.trim()" in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock transfer item product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /inventory/stock-transfers" in docs
    assert "Stock transfer product" in docs


@pytest.mark.asyncio
async def test_stock_transfer_item_product_id_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip286 From", code=f"F286{suffix[:4]}"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip286 To", code=f"T286{suffix[:4]}"
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
    await db_session.commit()

    body_base = {
        "from_warehouse_id": from_wh.id,
        "to_warehouse_id": to_wh.id,
        "submit": False,
    }

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.post(
            "/api/v1/inventory/stock-transfers",
            headers=admin,
            json={**body_base, "items": [{"product_id": bad, "quantity": 1}]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={**body_base, "items": [{"quantity": 1}]},
    )
    assert omit.status_code == 422, omit.text

    ok = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            **body_base,
            "items": [
                {
                    "product_id": f"  {str(seed['p1'].id).upper()}  ",
                    "quantity": 1,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["items"][0]["product_id"] == str(seed["p1"].id).lower()

    missing = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            **body_base,
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
