"""GET /inventory|/reports/inventory/movements reason Query OpenAPI Literal (BR-5.2/5.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.inventory import STOCK_ADJUSTMENT_REASONS
from app.schemas import StockAdjustReasonValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_adjust_reason_literal_covers_valid():
    lit = StockAdjustReasonValue.__args__[0]
    assert set(lit.__args__) == set(STOCK_ADJUSTMENT_REASONS)


def test_stock_adjust_reason_literal_schema():
    adapter = TypeAdapter(StockAdjustReasonValue)
    assert adapter.validate_python("damage") == "damage"
    assert adapter.validate_python("  Theft ") == "theft"
    assert adapter.validate_python("EXPIRY") == "expiry"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("broken")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_movement_reason_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Movement reason filter"' in page
    for v in ("damage", "theft", "expiry", "found", "lost"):
        assert f'value="{v}"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Movement reason Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "reason" in docs and "422" in docs
    assert "damage" in docs and "theft" in docs


@pytest.mark.asyncio
async def test_movement_reason_query_blank_invalid_422_and_ok(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for path in ("/api/v1/inventory/movements", "/api/v1/reports/inventory/movements"):
        blank = await ac.get(f"{path}?reason=", headers=headers)
        assert blank.status_code == 422, blank.text

        bad = await ac.get(f"{path}?reason=broken", headers=headers)
        assert bad.status_code == 422, bad.text

        ok = await ac.get(f"{path}?reason=Damage", headers=headers)
        assert ok.status_code == 200, ok.text

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, omit.text
