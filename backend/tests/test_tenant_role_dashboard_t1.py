"""Stage 80 T1 — Tenant role-scoped dashboards + permission filtering."""

from __future__ import annotations

import pyotp
import pytest

from app.rbac import ROLE_LABELS
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_company_admin_role_label_is_tenant_admin():
    assert ROLE_LABELS.get("company_admin") == "Tenant Admin"


@pytest.mark.asyncio
async def test_cashier_dashboard_omits_accounting_and_users(client):
    ac, _seeded = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=cash)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("view") == "cashier"
    assert "users" not in (data.get("sections") or [])
    assert "purchasing" not in (data.get("sections") or [])
    assert "expenses" not in (data.get("sections") or [])
    assert "accounting" not in (data.get("sections") or [])
    assert "user_stats" not in data
    assert "total_purchases" not in data
    assert "total_expenses" not in data
    # Cashier may still see sales/pos/inventory KPIs
    assert "daily_revenue" in data or "total_sales" in data


@pytest.mark.asyncio
async def test_executive_dashboard_includes_user_stats(client):
    """super_admin (2FA enrolled) exercises executive view + user_stats."""
    ac, seed = client
    headers = await _super(ac, seed)
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("view") == "executive"
    assert data.get("role_label") == "Super Admin"
    assert "user_stats" in data
    assert "total_users" in data["user_stats"]
    assert "users" in (data.get("sections") or [])
    assert "total_purchases" in data
    assert "total_expenses" in data


@pytest.mark.asyncio
async def test_store_manager_dashboard_view(client):
    ac, _seeded = client
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=mgr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("view") == "store_manager"
    # Store managers have users:read in RBAC — user_stats may appear
    assert "sections" in data


@pytest.mark.asyncio
async def test_cashier_cannot_list_users(client):
    ac, _seeded = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/users", headers=cash)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_alpha_admin_cannot_see_beta_users(client):
    ac, seed = client
    headers = await _super(ac, seed)
    # List users — all must belong to alpha (no cross-tenant leakage via API)
    r = await ac.get("/api/v1/users", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    items = body if isinstance(body, list) else (body.get("items") or body.get("users") or [])
    for u in items:
        email = (u.get("email") or "").lower()
        assert "@beta." not in email
        assert "beta@" not in email
