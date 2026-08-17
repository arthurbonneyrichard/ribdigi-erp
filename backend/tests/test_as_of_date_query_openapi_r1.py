"""Balance sheet / trial balance as_of Query OpenAPI honesty (BR-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import IsoDateQueryValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

PATHS = (
    "/api/v1/accounting/trial-balance",
    "/api/v1/reports/trial-balance",
    "/api/v1/accounting/balance-sheet",
    "/api/v1/reports/balance-sheet",
)


def test_iso_date_query_schema_for_as_of():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-17 ") == "2026-08-17"
    assert adapter.validate_python("2026-08-17T12:00:00") == "2026-08-17T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01", "2026-02-30"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_as_of_date_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Trial balance as of date"' in accounting
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report as of date"' in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "BS/TB as_of Query OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "IsoDateQueryValue" in docs
    assert "Trial balance as of date" in docs
    assert "Report as of date" in docs


@pytest.mark.asyncio
async def test_as_of_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for path in PATHS:
        blank = await ac.get(f"{path}?as_of=", headers=headers)
        assert blank.status_code == 422, (path, blank.text)

        bad = await ac.get(f"{path}?as_of=not-a-date", headers=headers)
        assert bad.status_code == 422, (path, bad.text)

        slash = await ac.get(f"{path}?as_of=01/02/2024", headers=headers)
        assert slash.status_code == 422, (path, slash.text)

        ok = await ac.get(f"{path}?as_of=2026-08-17", headers=headers)
        assert ok.status_code == 200, (path, ok.text)
        body = ok.json()["data"]
        assert isinstance(body, dict)
        assert body.get("mode") in {"journals", "balances"} or "assets" in body or "rows" in body

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, (path, omit.text)
