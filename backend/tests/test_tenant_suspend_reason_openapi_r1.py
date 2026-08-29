"""TenantSuspendRequest.reason OpenAPI honesty (platform + company self-suspend)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import TenantSuspendRequest
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_tenant_suspend_reason_schema():
    ok = TenantSuspendRequest.model_validate({"reason": "  Non-payment Q3  "})
    assert ok.reason == "Non-payment Q3"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            TenantSuspendRequest.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        TenantSuspendRequest.model_validate({})


def test_tenant_suspend_reason_ui_and_docs():
    plat = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tenant suspend reason"' in plat
    assert 'aria-label="Tenant suspend reason"' in company
    assert "aria-label={`Suspend tenant ${t.id}`}" in plat
    assert 'aria-label="Suspend company"' in company
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "TenantSuspendReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TenantSuspendReasonValue" in docs


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tenant_suspend_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await _super(ac, seed)
    slug = seed["t2"].slug
    suffix = uuid4().hex[:8]
    tag = f"TIP195 suspend {suffix}"

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/tenants/{slug}/suspend",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/tenants/{slug}/suspend",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "suspended"
    assert body["suspended_reason"] == tag

    act = await ac.post(f"/api/v1/tenants/{slug}/activate", headers=headers, json={})
    assert act.status_code == 200, act.text
    assert act.json()["data"]["status"] == "active"
