"""Stock count variance report Query warehouse_id / store_id ∈ UuidIdValue (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)
_PATH = "/api/v1/reports/inventory/stock-counts"
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_stock_count_report_location_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_stock_count_report_location_query_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count report warehouse_id Query OpenAPI" in agents
    assert "Stock count report store_id Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/reports/inventory/stock-counts" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_stock_count_report_location_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for key, bad_token in (
        ("warehouse_id", "wh_001"),
        ("store_id", "store_001"),
    ):
        for bad in ("", "!!!", "http://evil", "not-a-uuid", bad_token):
            resp = await ac.get(f"{_PATH}?{key}={bad}", headers=headers)
            assert resp.status_code == 422, (key, bad, resp.text)

        missing = await ac.get(
            f"{_PATH}?{key}={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
