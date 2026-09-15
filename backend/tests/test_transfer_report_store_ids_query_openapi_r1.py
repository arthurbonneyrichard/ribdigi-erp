"""Transfer report Query store_id / from_store_id / to_store_id ∈ UuidIdValue (BR-13.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)
_PATH = "/api/v1/reports/inventory/transfers"
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_transfer_report_store_ids_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_transfer_report_store_ids_query_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Transfer report store_id Query OpenAPI" in agents
    assert "Transfer report from_store_id Query OpenAPI" in agents
    assert "Transfer report to_store_id Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "/reports/inventory/transfers" in docs
    assert "UuidIdValue" in docs
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "params.set('store_id', storeTrim)" in reports


@pytest.mark.asyncio
async def test_transfer_report_store_ids_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for key in ("store_id", "from_store_id", "to_store_id"):
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
            resp = await ac.get(f"{_PATH}?{key}={bad}", headers=headers)
            assert resp.status_code == 422, (key, bad, resp.text)

        missing = await ac.get(
            f"{_PATH}?{key}={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
