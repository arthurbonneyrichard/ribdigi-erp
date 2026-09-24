"""Staff guide permission is role-granted, not company-admin-only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rbac import has_permission
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_staff_guide_requires_auth(client):
    ac, _seed = client
    anon = await ac.get("/api/v1/staff-guide")
    assert anon.status_code == 401


@pytest.mark.asyncio
async def test_cashier_can_download_staff_guide(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    resp = await ac.get("/api/v1/staff-guide", headers=headers)
    guide = ROOT / "backend/guides/RIBDIGI-ERP-Customer-User-Guide.pdf"
    if not guide.is_file():
        assert resp.status_code == 404
        return
    assert resp.status_code == 200, resp.text
    assert "pdf" in (resp.headers.get("content-type") or "").lower()
    assert resp.content[:4] == b"%PDF" or len(resp.content) > 100


@pytest.mark.asyncio
async def test_beta_cashier_cannot_use_alpha_tenant_header(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    headers["X-Tenant-ID"] = seed["t1"].id
    resp = await ac.get("/api/v1/staff-guide", headers=headers)
    assert resp.status_code == 403


def test_operational_roles_can_download_staff_guide():
    for role in (
        "store_manager",
        "sales_officer",
        "inventory_officer",
        "accountant",
        "cashier",
        "company_admin",
    ):
        assert has_permission(role, "staff_guide", "read")
        assert has_permission(role, "staff_guide", "download")


def test_guide_route_checks_staff_guide_permission():
    route = (ROOT / "frontend/app/guides/customer/route.ts").read_text(encoding="utf-8")
    assert "/staff-guide" in route
    assert "Only a company administrator" not in route
    dash = (ROOT / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "canDownloadStaffGuide" in dash
    assert "/staff-guide" in dash
    assert "role === 'company_admin' &&" not in dash
