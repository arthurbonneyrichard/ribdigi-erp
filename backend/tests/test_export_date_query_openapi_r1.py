"""GET /reports/export from_date/to_date/date/as_of Query OpenAPI honesty (BR-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_iso_date_query_schema_for_export():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-17 ") == "2026-08-17"
    assert adapter.validate_python("2026-08-17T12:00:00") == "2026-08-17T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01", "2026-02-30"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_export_date_ui_and_docs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report from date"' in reports
    assert 'aria-label="Report to date"' in reports
    assert 'aria-label="Report as of date"' in reports
    assert "/reports/export" in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report export date Query OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "IsoDateQueryValue" in docs
    assert "Report From/To/as of date" in docs


@pytest.mark.asyncio
async def test_export_date_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    base = "/api/v1/reports/export?report_type=cash_flow&format=csv"

    for param in ("from_date", "to_date", "date", "as_of"):
        blank = await ac.get(f"{base}&{param}=", headers=headers)
        assert blank.status_code == 422, (param, blank.text)

        bad = await ac.get(f"{base}&{param}=not-a-date", headers=headers)
        assert bad.status_code == 422, (param, bad.text)

        slash = await ac.get(f"{base}&{param}=01/02/2024", headers=headers)
        assert slash.status_code == 422, (param, slash.text)

    ok = await ac.get(
        f"{base}&from_date=2020-01-01&to_date=2099-12-31",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.headers.get("content-type", "").startswith("text/csv") or "csv" in (
        ok.headers.get("content-disposition") or ""
    ).lower() or ok.content

    ok_as_of = await ac.get(
        "/api/v1/reports/export?report_type=trial_balance&format=csv&as_of=2026-08-17",
        headers=headers,
    )
    assert ok_as_of.status_code == 200, ok_as_of.text

    omit = await ac.get(base, headers=headers)
    assert omit.status_code == 200, omit.text
