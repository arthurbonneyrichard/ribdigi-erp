"""Staff guide permission is role-granted, not company-admin-only."""

from __future__ import annotations

from pathlib import Path

from app.rbac import has_permission

ROOT = Path(__file__).resolve().parents[2]


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
    assert "staff_guide" in route
    assert "Only a company administrator" not in route
    dash = (ROOT / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "canDownloadStaffGuide" in dash
    assert "role === 'company_admin' &&" not in dash
