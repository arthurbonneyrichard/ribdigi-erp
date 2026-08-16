"""GET /reports/inventory/valuation method Query OpenAPI Literal (BR-14.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.reports import SUPPORTED_VALUATION_METHODS
from app.schemas import InventoryValuationMethodValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_valuation_method_literal_covers_supported():
    lit = InventoryValuationMethodValue.__args__[0]
    assert set(lit.__args__) == set(SUPPORTED_VALUATION_METHODS)


def test_inventory_valuation_method_literal_schema():
    adapter = TypeAdapter(InventoryValuationMethodValue)
    assert adapter.validate_python("standard") == "standard"
    assert adapter.validate_python("  Standard ") == "standard"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("fifo")
    with pytest.raises(ValidationError):
        adapter.validate_python("lifo")
    with pytest.raises(ValidationError):
        adapter.validate_python("weighted_average")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_inventory_valuation_method_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'value="standard"' in page
    assert "Valuation method" in page
    assert "valuationMethod" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Inventory valuation method OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "inventory/valuation" in docs
    assert "422" in docs
    assert "Valuation method" in docs


@pytest.mark.asyncio
async def test_inventory_valuation_method_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/inventory/valuation?method=", headers=headers)
    assert blank.status_code == 422, blank.text

    fifo = await ac.get("/api/v1/reports/inventory/valuation?method=fifo", headers=headers)
    assert fifo.status_code == 422, fifo.text

    ok = await ac.get(
        "/api/v1/reports/inventory/valuation?method=Standard",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["method"] == "standard"

    omit = await ac.get("/api/v1/reports/inventory/valuation", headers=headers)
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["method"] == "standard"
