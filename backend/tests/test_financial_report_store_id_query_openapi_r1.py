"""Financial report Query store_id ∈ UuidIdValue OpenAPI honesty (BR-14.5)."""

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
    "/api/v1/accounting/profit-loss",
    "/api/v1/reports/profit-loss",
    "/api/v1/accounting/trial-balance",
    "/api/v1/reports/trial-balance",
    "/api/v1/accounting/balance-sheet",
    "/api/v1/reports/balance-sheet",
    "/api/v1/reports/cash-flow",
)


def test_financial_report_store_id_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_financial_report_store_id_query_ui_and_docs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report financial store filter"' in reports
    assert "params.set('store_id', storeTrim)" in reports
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="P&L store filter"' in accounting
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Financial report store_id Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_financial_report_store_id_query_blank_invalid_422(client):
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

    export = await ac.get(
        "/api/v1/reports/export?report_type=profit_loss&format=csv&store_id=store_001",
        headers=headers,
    )
    assert export.status_code == 422, export.text
