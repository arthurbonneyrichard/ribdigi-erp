"""Warehouse warehouse_type OpenAPI Literal (BR-2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import WarehouseCreate, WarehouseUpdate

ROOT = Path(__file__).resolve().parents[2]


def test_warehouse_type_literal_create():
    ok = WarehouseCreate.model_validate(
        {"name": "A", "code": "WH-A", "warehouse_type": "cold_storage"}
    )
    assert ok.warehouse_type == "cold_storage"
    # omit → default retail
    defaulted = WarehouseCreate.model_validate({"name": "B", "code": "WH-B"})
    assert defaulted.warehouse_type == "retail"
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate(
            {"name": "C", "code": "WH-C", "warehouse_type": ""}
        )
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate(
            {"name": "D", "code": "WH-D", "warehouse_type": "   "}
        )
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate(
            {"name": "E", "code": "WH-E", "warehouse_type": "vault"}
        )


def test_warehouse_type_literal_update():
    ok = WarehouseUpdate.model_validate({"warehouse_type": "bulk"})
    assert ok.warehouse_type == "bulk"
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"warehouse_type": "vault"})
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"warehouse_type": ""})


def test_warehouse_type_ui_and_docs():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "cold_storage" in stores
    assert 'value="retail"' in stores
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "warehouse_type" in api
    assert "Literal" in api or "omit/blank/invalid → **422**" in api
