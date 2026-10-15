"""Cashier system role: POS (and till credit) only — other modules 403."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rbac import has_permission, permissions_for_role
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


def test_cashier_permission_map_keeps_till_credit_not_ap():
    perms = permissions_for_role("cashier")
    assert "write" in perms["pos"] and "read" in perms["pos"]
    assert "write" in perms["credit"]
    assert "read" not in perms.get("credit", [])
    assert "purchasing" not in perms
    assert "accounting" not in perms
    assert "reports" not in perms
    assert "users" not in perms
    assert has_permission("hotel_cashier", "hotel", "read")
    assert has_permission("company_admin", "purchasing", "write")


@pytest.mark.asyncio
async def test_cashier_api_denies_back_office_modules(client):
    ac, seed = client
    headers = await _cashier(ac)

    users = await ac.get("/api/v1/users", headers=headers)
    assert users.status_code == 403

    purchasing = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 1}]},
    )
    assert purchasing.status_code == 403

    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 403

    reports = await ac.get("/api/v1/reports/inventory/balance", headers=headers)
    assert reports.status_code == 403

    aging = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert aging.status_code == 403

    adjust = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=headers,
        json={"quantity": 1, "reason": "found"},
    )
    assert adjust.status_code == 403

    supplier_pay = await ac.post(
        "/api/v1/suppliers/00000000-0000-4000-8000-000000000099/payments",
        headers=headers,
        json={
            "supplier_id": "00000000-0000-4000-8000-000000000099",
            "amount": 1,
        },
    )
    assert supplier_pay.status_code == 403, supplier_pay.text

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    admin_pay = await ac.post(
        "/api/v1/suppliers/00000000-0000-4000-8000-000000000099/payments",
        headers=admin,
        json={
            "supplier_id": "00000000-0000-4000-8000-000000000099",
            "amount": 1,
        },
    )
    assert admin_pay.status_code == 404, admin_pay.text


@pytest.mark.asyncio
async def test_cashier_can_use_pos_search(client):
    ac, _seed = client
    headers = await _cashier(ac)
    search = await ac.get("/api/v1/pos/products/search", headers=headers, params={"q": "a"})
    assert search.status_code == 200, search.text


def test_shell_cashier_nav_and_people_children_wired():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "CASHIER_NAV_MODULES" in shell
    assert "unauthorizedNavRedirect" in shell
    assert "navAllowlistFromPermissions" in shell
    assert "navAllowlistForRole" in shell
    assert "ROLE_NAV_MODULES[role] ?? ROLE_NAV_MODULES.cashier" not in shell
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "export function navAllowlistFromPermissions" in nav
    assert "ALWAYS_LIST_NAV_GROUP_IDS.has(group.id)" in shell
    assert "nav-group-static" in shell
    assert "['dashboard', 'inventory', 'pos', 'sales', 'notifications', 'security']" not in shell
