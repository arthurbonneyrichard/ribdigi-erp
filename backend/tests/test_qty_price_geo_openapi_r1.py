"""OpenAPI honesty tips #527–#532: qty/price/dims/geo Values."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    FiniteQtyValue,
    LatitudeValue,
    LineItem,
    LongitudeValue,
    NonNegativeQtyValue,
    PartyCreate,
    PositiveQtyValue,
    ProductCreate,
    StockAdjust,
    StoreReorderPolicyUpdate,
    UnitOfMeasureCreate,
    WarehouseCreate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_pos = TypeAdapter(PositiveQtyValue)
_nn = TypeAdapter(NonNegativeQtyValue)
_fin = TypeAdapter(FiniteQtyValue)
_lat = TypeAdapter(LatitudeValue)
_lon = TypeAdapter(LongitudeValue)


def test_qty_price_geo_schema():
    assert _pos.validate_python(1) == 1.0
    assert _nn.validate_python(0) == 0.0
    assert _fin.validate_python(-3) == -3.0
    assert _lat.validate_python(5.6) == 5.6
    assert _lon.validate_python(-0.2) == -0.2

    for bad in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            _pos.validate_python(bad)
    for bad in (-1, float("inf"), float("nan"), 1e16):
        with pytest.raises(ValidationError):
            _nn.validate_python(bad)
    for bad in (float("inf"), float("nan"), 1e16):
        with pytest.raises(ValidationError):
            _fin.validate_python(bad)
    with pytest.raises(ValidationError):
        _lat.validate_python(91)
    with pytest.raises(ValidationError):
        _lon.validate_python(-181)

    LineItem.model_validate({"product_id": str(uuid4()), "quantity": 2})
    with pytest.raises(ValidationError):
        LineItem.model_validate({"product_id": str(uuid4()), "quantity": float("inf")})

    StockAdjust.model_validate({"quantity": -2, "reason": "damage"})
    with pytest.raises(ValidationError):
        StockAdjust.model_validate({"quantity": float("nan"), "reason": "damage"})

    ProductCreate.model_validate(
        {"name": "Widget", "sku": "W-1", "selling_price": 9.99, "weight": 1.2}
    )
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(
            {"name": "Widget", "sku": "W-1", "selling_price": float("inf")}
        )
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(
            {"name": "Widget", "sku": "W-2", "weight": -1}
        )

    PartyCreate.model_validate({"name": "Acme", "latitude": 5.6, "longitude": -0.1})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "Acme", "latitude": 100})

    StoreReorderPolicyUpdate.model_validate(
        {"product_id": str(uuid4()), "reorder_level": 5, "reorder_qty": 10}
    )
    with pytest.raises(ValidationError):
        StoreReorderPolicyUpdate.model_validate(
            {"product_id": str(uuid4()), "reorder_level": float("inf")}
        )

    WarehouseCreate.model_validate({"code": "WH1", "name": "Main", "capacity": 100})
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate(
            {"code": "WH2", "name": "Main", "capacity": float("nan")}
        )

    UnitOfMeasureCreate.model_validate(
        {"code": "CASE", "name": "Case", "conversion_ratio": 12}
    )
    with pytest.raises(ValidationError):
        UnitOfMeasureCreate.model_validate(
            {"code": "CASE", "name": "Case", "conversion_ratio": 0}
        )


def test_qty_price_geo_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Qty / geo Value aliases OpenAPI",
        "Line / movement quantity OpenAPI",
        "Product price OpenAPI",
        "Stock / reorder / capacity / dims OpenAPI",
        "Party GPS + UoM ratio OpenAPI",
    ):
        assert title in agents, title
    assert "PositiveQtyValue" in agents
    assert "LatitudeValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PositiveQtyValue" in docs
    assert "LatitudeValue" in docs
    assert "FiniteQtyValue" in docs

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Line quantity"' in sales
    assert 'aria-label="Line unit price"' in sales
    assert 'aria-label="Customer latitude"' in sales

    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product selling price"' in inv
    assert 'aria-label="Product weight"' in inv
    assert 'aria-label="Warehouse reorder level"' in inv
    assert 'aria-label="Unit conversion ratio"' in inv

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Warehouse capacity"' in stores
    assert 'aria-label="Store reorder level"' in stores

    purch = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Supplier latitude"' in purch


@pytest.mark.asyncio
async def test_qty_price_geo_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "BadPrice", "sku": "BADPRICE1", "selling_price": "inf"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "BadGeo", "latitude": 91},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"code": "BADCAP", "name": "Bad Cap", "capacity": "nan"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "BADRATIO", "name": "Bad Ratio", "conversion_ratio": 0},
    )
    assert resp.status_code == 422, resp.text

    pid = str(uuid4())
    resp = await ac.post(
        f"/api/v1/inventory/adjust/{pid}",
        headers=headers,
        json={"quantity": "inf", "reason": "damage"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.put(
        f"/api/v1/stores/{uuid4()}/reorder-policy",
        headers=headers,
        json={"product_id": str(uuid4()), "reorder_level": "inf", "reorder_qty": 1},
    )
    assert resp.status_code == 422, resp.text
