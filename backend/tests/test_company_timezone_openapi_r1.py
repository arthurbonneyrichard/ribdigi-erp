"""Company profile timezone IANA OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import TenantProfileUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_timezone_schema():
    bare = TenantProfileUpdate.model_validate({})
    assert bare.timezone is None

    ok = TenantProfileUpdate.model_validate({"timezone": "  Africa/Accra "})
    assert ok.timezone == "Africa/Accra"

    utc = TenantProfileUpdate.model_validate({"timezone": "UTC"})
    assert utc.timezone == "UTC"

    for bad in ("", " ", "Foo/Bar", "UTC+0", "GMT+1", "Africa/Accraa"):
        with pytest.raises(ValidationError):
            TenantProfileUpdate.model_validate({"timezone": bad})


def test_company_timezone_ui_and_docs():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company timezone"' in page
    assert "Timezone: {z}" in page
    assert 'placeholder="Timezone"' not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Company timezone OpenAPI" in agents
    assert "TimezoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TimezoneValue" in docs
    assert "Company **Timezone** select" in docs


@pytest.mark.asyncio
async def test_company_timezone_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", " ", "Foo/Bar", "UTC+0"):
        resp = await ac.patch(
            "/api/v1/tenants/me",
            headers=headers,
            json={"timezone": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"timezone": "africa/lagos"},
    )
    # ZoneInfo keys are case-sensitive; lower-case africa/lagos should 422
    # unless we coerce — current TimezoneValue only strips, so expect 422.
    # Prefer canonical IANA casing in the happy path below.
    assert ok.status_code == 422, ok.text

    ok2 = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"timezone": "Africa/Lagos"},
    )
    assert ok2.status_code == 200, ok2.text
    assert ok2.json()["data"].get("timezone") == "Africa/Lagos"

    restore = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"timezone": "Africa/Accra"},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["data"].get("timezone") == "Africa/Accra"
