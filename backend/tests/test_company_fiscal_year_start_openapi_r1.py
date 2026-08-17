"""Company profile fiscal_year_start MM-DD OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_fiscal_year_start_schema():
    bare = TenantProfileUpdate.model_validate({})
    assert bare.fiscal_year_start is None

    ok = TenantProfileUpdate.model_validate({"fiscal_year_start": " 04-01 "})
    assert ok.fiscal_year_start == "04-01"

    leap = TenantProfileUpdate.model_validate({"fiscal_year_start": "02-29"})
    assert leap.fiscal_year_start == "02-29"

    for bad in ("", " ", "1-1", "13-01", "00-01", "02-30", "ab-cd", "01/01", "2026-01-01"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"fiscal_year_start": bad})


def test_company_fiscal_year_start_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Fiscal year start"' in page
    assert 'pattern="(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company fiscal_year_start OpenAPI" in agents
    assert "FiscalYearStartValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "FiscalYearStartValue" in docs
    assert "Company **Fiscal year start** input" in docs


@pytest.mark.asyncio
async def test_company_fiscal_year_start_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", " ", "1-1", "13-01", "02-30", "ab-cd"):
        resp = await ac.patch(
            "/api/v1/tenants/me",
            headers=headers,
            json={"fiscal_year_start": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"fiscal_year_start": "04-01"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("fiscal_year_start") == "04-01"

    # null omit-style: explicit null should not wipe when schema allows None as no-op
    kept = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"fiscal_year_start": None},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"].get("fiscal_year_start") == "04-01"

    restore = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"fiscal_year_start": "01-01"},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["data"].get("fiscal_year_start") == "01-01"
