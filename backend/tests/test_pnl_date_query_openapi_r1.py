"""P&L from_date/to_date Query OpenAPI honesty (BR-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_iso_date_query_schema_for_pnl():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-17 ") == "2026-08-17"
    assert adapter.validate_python("2026-08-17T12:00:00") == "2026-08-17T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01", "2026-02-30"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_pnl_date_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="P&L from date"' in accounting
    assert 'aria-label="P&L to date"' in accounting
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report from date"' in reports
    assert 'aria-label="Report to date"' in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "P&L date Query OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "IsoDateQueryValue" in docs
    assert "P&L From/To date" in docs


@pytest.mark.asyncio
async def test_pnl_date_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for path in ("/api/v1/accounting/profit-loss", "/api/v1/reports/profit-loss"):
        blank = await ac.get(f"{path}?from_date=", headers=headers)
        assert blank.status_code == 422, blank.text

        bad = await ac.get(f"{path}?from_date=not-a-date", headers=headers)
        assert bad.status_code == 422, bad.text

        slash = await ac.get(f"{path}?to_date=01/02/2024", headers=headers)
        assert slash.status_code == 422, slash.text

        ok = await ac.get(
            f"{path}?from_date=2020-01-01&to_date=2099-12-31",
            headers=headers,
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()["data"]
        assert isinstance(body, dict)
        assert "revenue" in body or "net_profit" in body or "gross_profit" in body

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, omit.text
