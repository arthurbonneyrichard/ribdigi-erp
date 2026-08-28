"""StockTransferCreate warehouse ids ∈ UuidIdValue OpenAPI honesty (BR-5.2 / BR-13.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockTransferCreate, UuidIdValue
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID_FROM = "11111111-2222-3333-4444-555555555555"
_VALID_TO = "22222222-3333-4444-5555-666666666666"
_VALID_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_ITEMS = [{"product_id": _VALID_PRODUCT, "quantity": 1}]


def test_stock_transfer_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID_FROM}  ") == _VALID_FROM.lower()
    ok = StockTransferCreate.model_validate(
        {
            "from_warehouse_id": f"  {_VALID_FROM}  ",
            "to_warehouse_id": f"  {_VALID_TO}  ",
            "items": _ITEMS,
        }
    )
    assert ok.from_warehouse_id == _VALID_FROM.lower()
    assert ok.to_warehouse_id == _VALID_TO.lower()
    for field, bad in (
        ("from_warehouse_id", ""),
        ("from_warehouse_id", "!!!"),
        ("from_warehouse_id", "http://evil"),
        ("from_warehouse_id", "not-a-uuid"),
        ("from_warehouse_id", "wh_001"),
        ("to_warehouse_id", "wh_002"),
    ):
        with pytest.raises(ValidationError):
            StockTransferCreate.model_validate(
                {
                    "from_warehouse_id": _VALID_FROM,
                    "to_warehouse_id": _VALID_TO,
                    "items": _ITEMS,
                    field: bad,
                }
            )


def test_stock_transfer_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock transfer from warehouse"' in page
    assert 'aria-label="Stock transfer to warehouse"' in page
    assert "from_warehouse_id: xferFromWh.trim()" in page
    assert "to_warehouse_id: xferToWh.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock transfer warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stock transfer from warehouse" in docs
    assert "POST /inventory/stock-transfers" in docs


@pytest.mark.asyncio
async def test_stock_transfer_warehouse_id_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip296 From", code=f"F296{suffix[:4]}"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip296 To", code=f"T296{suffix[:4]}"
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

    item = {"product_id": seed["p1"].id, "quantity": 1}
    body_ok = {
        "from_warehouse_id": from_wh.id,
        "to_warehouse_id": to_wh.id,
        "submit": False,
        "items": [item],
    }

    for field, bad in (
        ("from_warehouse_id", ""),
        ("from_warehouse_id", "!!!"),
        ("from_warehouse_id", "http://evil"),
        ("from_warehouse_id", "not-a-uuid"),
        ("to_warehouse_id", "wh_002"),
    ):
        resp = await ac.post(
            "/api/v1/inventory/stock-transfers",
            headers=admin,
            json={**body_ok, field: bad},
        )
        assert resp.status_code == 422, (field, bad, resp.text)

    ok = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            **body_ok,
            "from_warehouse_id": f"  {str(from_wh.id).upper()}  ",
            "to_warehouse_id": f"  {str(to_wh.id).upper()}  ",
        },
    )
    assert ok.status_code == 200, ok.text

    missing = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={
            **body_ok,
            "from_warehouse_id": str(uuid4()),
        },
    )
    assert missing.status_code in (400, 404), missing.text
