"""Sales daily date Query OpenAPI honesty (BR-14.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

PATH = "/api/v1/reports/sales/daily"


def test_iso_date_query_schema_for_sales_daily():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-17 ") == "2026-08-17"
    assert adapter.validate_python("2026-08-17T12:00:00") == "2026-08-17T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01", "2026-02-30"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_sales_daily_date_ui_and_docs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report from date"' in reports
    assert 'aria-label="Report to date"' in reports
    assert "sales/daily" in reports
    assert "{ date: toDate || fromDate }" in reports or "date: toDate || fromDate" in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales daily date Query OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "IsoDateQueryValue" in docs
    assert "sales/daily" in docs


@pytest.mark.asyncio
async def test_sales_daily_date_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get(f"{PATH}?date=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get(f"{PATH}?date=not-a-date", headers=headers)
    assert bad.status_code == 422, bad.text

    slash = await ac.get(f"{PATH}?date=01/02/2024", headers=headers)
    assert slash.status_code == 422, slash.text

    ok = await ac.get(f"{PATH}?date=2020-01-01", headers=headers)
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert isinstance(body, dict)
    assert body.get("date") == "2020-01-01"

    omit = await ac.get(PATH, headers=headers)
    assert omit.status_code == 200, omit.text
    omit_body = omit.json()["data"]
    assert isinstance(omit_body, dict)
    assert omit_body.get("date")
