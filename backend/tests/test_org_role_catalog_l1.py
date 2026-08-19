"""Stage 85 L1 — Org-chart role catalog labels + system matrix UI."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.rbac import ROLE_ORG_CHART_LABELS, list_system_role_catalog
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_org_chart_labels_map_manager_and_tenant_admin():
    assert ROLE_ORG_CHART_LABELS["store_manager"] == "Manager"
    assert ROLE_ORG_CHART_LABELS["company_admin"] == "Tenant Admin"
    catalog = {r["role"]: r for r in list_system_role_catalog()}
    assert catalog["store_manager"]["org_chart_label"] == "Manager"
    assert catalog["company_admin"]["org_chart_label"] == "Tenant Admin"
    assert catalog["cashier"]["org_chart_label"] == "Cashier"
    assert catalog["accountant"]["org_chart_label"] == "Accountant"
    assert catalog["inventory_officer"]["org_chart_label"] == "Inventory Officer"
    assert catalog["sales_officer"]["org_chart_label"] == "Sales Officer"


@pytest.mark.asyncio
async def test_roles_api_includes_org_chart_label(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    r = await ac.get("/api/v1/roles", headers=admin)
    assert r.status_code == 200, r.text
    roles = r.json()["data"]
    by_role = {row["role"]: row for row in roles}
    assert by_role["store_manager"]["org_chart_label"] == "Manager"
    assert by_role["company_admin"]["org_chart_label"] == "Tenant Admin"
    assert "platform_super_admin" not in by_role


def test_permissions_page_has_system_readonly_matrix():
    page = (ROOT / "frontend/app/admin/permissions/page.tsx").read_text(encoding="utf-8")
    assert "System roles (read-only)" in page or "read-only" in page
    assert "org_chart_label" in page
    assert "disabled" in page


def test_roles_page_shows_org_chart_column():
    page = (ROOT / "frontend/app/admin/roles/page.tsx").read_text(encoding="utf-8")
    assert "Org chart" in page or "org_chart" in page
    assert "Manager" in page or "org_chart_label" in page
