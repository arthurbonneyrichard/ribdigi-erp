"""TenantSubscriptionAssign.start_at OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantSubscriptionAssign
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_subscription_start_at_schema():
    base = {"package_code": "starter", "term_value": 6}
    omit = TenantSubscriptionAssign.model_validate(base)
    assert omit.start_at is None
    ok = TenantSubscriptionAssign.model_validate({**base, "start_at": " 2026-01-15 "})
    assert ok.start_at == "2026-01-15"
    iso = TenantSubscriptionAssign.model_validate(
        {**base, "start_at": "2026-01-15T12:00:00"}
    )
    assert iso.start_at == "2026-01-15T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            TenantSubscriptionAssign.model_validate({**base, "start_at": bad})


def test_subscription_start_at_ui_and_docs():
    page = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Subscription start date"' in page
    assert "subForm.start_at.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Subscription start_at OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Subscription start date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_subscription_start_at_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    tenant_ref = seed["t1"].slug

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            f"/api/v1/tenants/{tenant_ref}/subscription",
            headers=headers,
            json={
                "package_code": "starter",
                "term_value": 1,
                "term_unit": "months",
                "start_at": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/tenants/{tenant_ref}/subscription",
        headers=headers,
        json={
            "package_code": "starter",
            "term_value": 1,
            "term_unit": "months",
            "start_at": "2026-01-15",
            "activate": True,
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    sub = data.get("subscription") or {}
    starts = sub.get("subscription_starts_at") or data.get("subscription_starts_at")
    assert str(starts or "").startswith("2026-01-15"), ok.text

    omit = await ac.post(
        f"/api/v1/tenants/{tenant_ref}/subscription",
        headers=headers,
        json={
            "package_code": "starter",
            "term_value": 1,
            "term_unit": "months",
            "activate": True,
        },
    )
    assert omit.status_code == 200, omit.text
