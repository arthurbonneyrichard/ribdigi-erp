"""StockCountCreate.product_ids ∈ list[UuidIdValue] OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockCountCreate
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_WH = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_P = "11111111-2222-3333-4444-555555555555"


def test_stock_count_product_ids_schema():
    omit = StockCountCreate.model_validate({"warehouse_id": _WH})
    assert omit.product_ids is None
    ok = StockCountCreate.model_validate(
        {"warehouse_id": _WH, "product_ids": [f"  {_P}  "]}
    )
    assert ok.product_ids == [_P]
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        with pytest.raises(ValidationError):
            StockCountCreate.model_validate(
                {"warehouse_id": _WH, "product_ids": [bad]}
            )


def test_stock_count_product_ids_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count product_ids OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "product_ids" in docs
    assert "list[UuidIdValue]" in docs


@pytest.mark.asyncio
async def test_stock_count_product_ids_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip414 Count Store", code="T414"
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
        resp = await ac.post(
            "/api/v1/inventory/stock-counts",
            headers=headers,
            json={"warehouse_id": warehouse_id, "product_ids": [bad]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={
            "warehouse_id": warehouse_id,
            "product_ids": [f"  {str(uuid4()).upper()}  "],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
