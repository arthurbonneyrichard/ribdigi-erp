"""GET /reports/tax/filing (+ export) jurisdiction Query OpenAPI (Tax UI filter)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import TypeAdapter, ValidationError

from app import tax_filings as tax_filings_svc
from app.schemas import TaxFilingJurisdictionValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _literal_values(annotated) -> set[str]:
    cur: object = annotated
    for _ in range(6):
        origin = get_origin(cur)
        args = get_args(cur)
        if origin is Literal:
            return set(args)
        if not args:
            break
        cur = args[0]
    raise AssertionError(f"Could not unwrap Literal from {annotated!r}")


def test_tax_filing_jurisdiction_literal_matches_supported():
    adapter = TypeAdapter(TaxFilingJurisdictionValue)
    for code in tax_filings_svc.SUPPORTED:
        assert adapter.validate_python(code) == code
        assert adapter.validate_python(f"  {code.lower()} ") == code

    lit_args = _literal_values(TaxFilingJurisdictionValue)
    assert lit_args == set(tax_filings_svc.SUPPORTED)

    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("NG")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_tax_filing_jurisdiction_ui_and_docs():
    page = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "filingJurisdictionFilter" in page
    assert 'aria-label="Tax filing jurisdiction filter"' in page
    assert 'value="GH"' in page
    assert "Tenant default" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tax filing jurisdiction Query OpenAPI" in agents
    assert "TaxFilingJurisdictionValue" in agents
    assert "filingJurisdictionFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TaxFilingJurisdictionValue" in docs or "tax_filings.SUPPORTED" in docs
    assert "GET /reports/tax/filing" in docs
    assert "filingJurisdictionFilter" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_tax_filing_jurisdiction_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/tax/filing?jurisdiction=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/reports/tax/filing?jurisdiction=NG", headers=headers)
    assert bad.status_code == 422, bad.text

    omit = await ac.get("/api/v1/reports/tax/filing", headers=headers)
    assert omit.status_code == 200, omit.text
    omit_data = omit.json()["data"]
    assert omit_data.get("jurisdiction")
    assert "supported_jurisdictions" in omit_data

    gh = await ac.get("/api/v1/reports/tax/filing?jurisdiction=gh", headers=headers)
    assert gh.status_code == 200, gh.text
    gh_data = gh.json()["data"]
    assert gh_data.get("jurisdiction") == "GH"
    assert gh_data.get("government") is not None

    exp_blank = await ac.get(
        "/api/v1/reports/export?report_type=tax_filing_gh&format=csv&jurisdiction=",
        headers=headers,
    )
    assert exp_blank.status_code == 422, exp_blank.text

    exp_bad = await ac.get(
        "/api/v1/reports/export?report_type=tax_filing_gh&format=csv&jurisdiction=NG",
        headers=headers,
    )
    assert exp_bad.status_code == 422, exp_bad.text

    exp_ok = await ac.get(
        "/api/v1/reports/export?report_type=tax_filing_gh&format=csv&jurisdiction=GH",
        headers=headers,
    )
    assert exp_ok.status_code == 200, exp_ok.text
    assert exp_ok.headers.get("content-type", "").startswith("text/") or "csv" in (
        exp_ok.headers.get("content-type") or ""
    ) or exp_ok.content
