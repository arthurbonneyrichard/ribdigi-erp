"""GET /inventory|/reports/inventory/movements movement_type Query OpenAPI Literal (BR-5.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.inventory import MOVEMENT_TYPES
from app.schemas import MovementTypeValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_movement_type_literal_covers_valid():
    lit = MovementTypeValue.__args__[0]
    assert set(lit.__args__) == set(MOVEMENT_TYPES)


def test_movement_type_literal_schema():
    adapter = TypeAdapter(MovementTypeValue)
    assert adapter.validate_python("stock_in") == "stock_in"
    assert adapter.validate_python("  Transfer_Cancel ") == "transfer_cancel"
    assert adapter.validate_python("OPENING_STOCK") == "opening_stock"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("receive")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_movement_type_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Movement type filter"' in page
    for v in (
        "stock_in",
        "stock_out",
        "opening_stock",
        "adjustment",
        "transfer_out",
        "transfer_in",
        "transfer_cancel",
    ):
        assert f'value="{v}"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Movement type Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "movement_type" in docs
    assert "422" in docs
    assert "transfer_cancel" in docs


@pytest.mark.asyncio
async def test_movement_type_query_blank_invalid_422_and_ok(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for path in ("/api/v1/inventory/movements", "/api/v1/reports/inventory/movements"):
        blank = await ac.get(f"{path}?movement_type=", headers=headers)
        assert blank.status_code == 422, blank.text

        bad = await ac.get(f"{path}?movement_type=receive", headers=headers)
        assert bad.status_code == 422, bad.text

        ok = await ac.get(f"{path}?movement_type=Stock_In", headers=headers)
        assert ok.status_code == 200, ok.text
        body = ok.json()["data"]
        assert isinstance(body, (list, dict))

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, omit.text
