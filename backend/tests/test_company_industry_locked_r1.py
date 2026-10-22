"""Company users cannot change tenant industry; label-only on Company profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_page_industry_is_label_only():
    page = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company industry"' in page
    assert "industry:" not in page.split("async function save()")[1].split("});")[0]
    assert "Business type:" in page


@pytest.mark.asyncio
async def test_company_admin_cannot_change_industry(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    denied = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"industry": "restaurant"},
    )
    assert denied.status_code == 403, denied.text
    assert "cannot be changed" in denied.json()["detail"].lower()

    me = await ac.get("/api/v1/tenants/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["industry"] == "retail"
    assert me.json()["data"]["industry_label"] == "Retail"
