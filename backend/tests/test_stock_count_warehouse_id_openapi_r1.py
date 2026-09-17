"""StockCountCreate.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockCountCreate, UuidIdValue
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_stock_count_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    assert _uuid.validate_python(_VALID.lower()) == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)

    ok = StockCountCreate.model_validate({"warehouse_id": f"  {_VALID}  "})
    assert ok.warehouse_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        with pytest.raises(ValidationError):
            StockCountCreate.model_validate({"warehouse_id": bad})
    with pytest.raises(ValidationError):
        StockCountCreate.model_validate({})


def test_stock_count_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock count warehouse"' in page
    assert "warehouse_id: countWarehouseId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "Stock count warehouse" in docs


@pytest.mark.asyncio
async def test_stock_count_warehouse_id_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip268 Count Store", code="T268"
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

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            "/api/v1/inventory/stock-counts",
            headers=headers,
            json={"warehouse_id": bad, "product_ids": [seed["p1"].id]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={
            "warehouse_id": f"  {str(warehouse_id).upper()}  ",
            "product_ids": [seed["p1"].id],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["warehouse_id"] == str(warehouse_id).lower()

    missing = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": str(uuid4()), "product_ids": [seed["p1"].id]},
    )
    assert missing.status_code in (400, 404), missing.text
