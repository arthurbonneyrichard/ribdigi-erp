"""Inventory report Query store_id ∈ UuidIdValue OpenAPI honesty (BR-14.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_PATHS = (
    "/api/v1/reports/inventory/low-stock",
    "/api/v1/reports/inventory/expiry",
    "/api/v1/reports/inventory/balance",
    "/api/v1/reports/inventory/valuation",
)


def test_inventory_report_store_id_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_inventory_report_store_id_query_ui_and_docs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report inventory store filter"' in reports
    assert "params.set('store_id', storeTrim)" in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Inventory report store_id Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/reports/inventory/low-stock" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_inventory_report_store_id_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
            resp = await ac.get(f"{path}?store_id={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?store_id={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
