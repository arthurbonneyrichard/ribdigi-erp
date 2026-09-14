"""First-class ``export`` / ``view_cost`` RBAC actions (engine + key surfaces).

Does not claim store-scoped RBAC Complete or overall RBAC Complete.
"""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.dashboard_scope import (
    omit_ai_dead_stock_cost,
    omit_bi_cost_fields,
    omit_inventory_report_cost,
    omit_product_cost_price,
    omit_stock_count_variance_cost,
)
from app.rbac import (
    ALLOWED_ACTIONS,
    ensure_permission_dependencies,
    has_permission,
    normalize_permissions_map,
    permissions_for_role,
)
from tests.conftest import auth_headers


def test_allowed_actions_include_export_and_view_cost():
    assert "export" in ALLOWED_ACTIONS
    assert "view_cost" in ALLOWED_ACTIONS
    assert "approve" in ALLOWED_ACTIONS


def test_normalize_accepts_export_view_cost_and_aliases():
    out = normalize_permissions_map(
        {"inventory": ["export", "view_cost"], "sales.cost": True, "reports:csv": True},
        allow_wildcard=False,
    )
    assert "export" in out["inventory"] and "view_cost" in out["inventory"]
    assert "view_cost" in out["sales"]
    assert "export" in out["reports"]


def test_export_view_cost_imply_read_on_save():
    out = ensure_permission_dependencies(
        {"inventory": ["export"], "reports": ["view_cost"]},
        allow_wildcard=False,
    )
    assert out["inventory"][0] == "read" and "export" in out["inventory"]
    assert out["reports"][0] == "read" and "view_cost" in out["reports"]


def test_system_role_grants_export_without_view_cost_for_store_manager():
    sm = permissions_for_role("store_manager")
    assert "export" in sm["inventory"]
    assert "view_cost" not in sm["inventory"]
    assert has_permission("store_manager", "inventory", "export", overrides=sm)
    assert not has_permission("store_manager", "inventory", "view_cost", overrides=sm)

    acct = permissions_for_role("accountant")
    assert "view_cost" in acct["inventory"]
    assert "export" in acct["reports"]
    assert has_permission("accountant", "inventory", "view_cost", overrides=acct)

    cash = permissions_for_role("cashier")
    assert "export" not in (cash.get("inventory") or [])
    assert not has_permission("cashier", "inventory", "export", overrides=cash)


def test_omit_product_cost_price_uses_view_cost_when_claims_present():
    sm_claims = {
        "role": "store_manager",
        "permissions": permissions_for_role("store_manager"),
    }
    assert omit_product_cost_price(["store-1"], claims=sm_claims) is True

    admin_claims = {
        "role": "company_admin",
        "permissions": {"*": ["*"]},
    }
    assert omit_product_cost_price(None, claims=admin_claims) is False

    # Legacy fallback when claims omitted
    assert omit_product_cost_price(["store-1"]) is True
    assert omit_product_cost_price(None) is False


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_products_export_requires_export_action(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    slug = "inv_read_only_export"
    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": slug,
            "label": "Inv Read Only",
            "permissions": {
                "inventory": ["read"],
                "dashboard": ["read"],
                "security": ["read", "write"],
                "notifications": ["read", "write"],
            },
            "record_scope": "all",
        },
    )
    assert created.status_code == 200, created.text

    user = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "invread@alpha.example.com",
            "full_name": "Inv Read",
            "password": "SecurePass123!",
            "role": slug,
        },
    )
    assert user.status_code == 200, user.text
    uid = user.json()["data"]["id"]
    row = await db_session.get(m.User, uid)
    assert row is not None
    row.email_verified = True
    await db_session.commit()

    read_h = await auth_headers(ac, email="invread@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/products/export", headers=read_h)
    assert denied.status_code == 403, denied.text
    assert "inventory:export" in denied.text

    # Elevate custom role + user snapshot with export
    put = await ac.put(
        f"/api/v1/roles/{slug}/permissions",
        headers=headers,
        json={
            "permissions": {
                "inventory": ["read", "export"],
                "dashboard": ["read"],
                "security": ["read", "write"],
                "notifications": ["read", "write"],
            },
            "record_scope": "all",
        },
    )
    assert put.status_code == 200, put.text
    row = await db_session.get(m.User, uid)
    row.permissions = put.json()["data"]["permissions"]
    # Membership override must match user snapshot for company workspace.
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == uid,
                m.UserCompanyMembership.company_id == seed["c1"].id,
            )
        )
    ).scalar_one_or_none()
    if mem is not None:
        mem.permissions = dict(row.permissions)
    await db_session.commit()

    allowed_h = await auth_headers(ac, email="invread@alpha.example.com", tenant_slug="alpha")
    allowed = await ac.get("/api/v1/products/export", headers=allowed_h)
    assert allowed.status_code == 200, allowed.text
    assert "text/csv" in allowed.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_store_manager_product_cost_redacted_admin_intact(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = m.Product(
        tenant_id=tid,
        company_id=cid,
        sku="COST-RBAC-1",
        name="Cost Probe",
        selling_price=20,
        cost_price=7.5,
        stock_qty=3,
        is_active=True,
    )
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        code="MGR-COST",
        name="Mgr Cost Store",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add_all([product, store])
    await db_session.commit()

    mgr_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    mgr_list = await ac.get("/api/v1/products", headers=mgr_h)
    assert mgr_list.status_code == 200, mgr_list.text
    probe = next(r for r in mgr_list.json()["data"] if r.get("sku") == "COST-RBAC-1")
    assert probe.get("cost_price") is None

    admin_h = await _super(ac, seed)
    admin_list = await ac.get("/api/v1/products", headers=admin_h)
    assert admin_list.status_code == 200, admin_list.text
    aprobe = next(r for r in admin_list.json()["data"] if r.get("sku") == "COST-RBAC-1")
    assert float(aprobe.get("cost_price") or 0) == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_sales_invoice_export_denied_without_export(client):
    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    res = await ac.get("/api/v1/sales/invoices/export", headers=cash)
    assert res.status_code == 403, res.text
    assert "sales:export" in res.text


@pytest.mark.asyncio
async def test_reports_export_allowed_for_store_manager_with_export(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    existing = (
        await db_session.execute(
            select(m.Store).where(m.Store.tenant_id == tid, m.Store.manager_id == mgr.id)
        )
    ).scalars().first()
    if existing is None:
        db_session.add(
            m.Store(
                tenant_id=tid,
                company_id=cid,
                code="MGR-RPT",
                name="Mgr Report Store",
                manager_id=mgr.id,
                is_active=True,
            )
        )
        await db_session.commit()

    mgr_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    res = await ac.get(
        "/api/v1/reports/export",
        headers=mgr_h,
        params={"report_type": "sales_daily", "format": "csv"},
    )
    assert res.status_code == 200, res.text
    assert "text/csv" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_custom_role_save_export_view_cost_via_api(client):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "cost_export_ops",
            "label": "Cost Export Ops",
            "permissions": {"inventory": ["export", "view_cost"], "reports": ["export"]},
            "record_scope": "own",
        },
    )
    assert created.status_code == 200, created.text
    perms = created.json()["data"]["permissions"]
    assert "read" in perms["inventory"]
    assert "export" in perms["inventory"]
    assert "view_cost" in perms["inventory"]
    assert "read" in perms["reports"] and "export" in perms["reports"]


def test_unified_cost_omit_helpers_use_view_cost_when_claims_present():
    sm = {
        "role": "store_manager",
        "permissions": permissions_for_role("store_manager"),
    }
    acct = {
        "role": "accountant",
        "permissions": permissions_for_role("accountant"),
    }
    admin = {"role": "company_admin", "permissions": {"*": ["*"]}}

    assert omit_inventory_report_cost(["wh-1"], claims=sm) is True
    assert omit_inventory_report_cost(["wh-1"], claims=acct) is False
    assert omit_ai_dead_stock_cost(["wh-1"], claims=sm) is True
    assert omit_ai_dead_stock_cost(["wh-1"], claims=acct) is False
    assert omit_stock_count_variance_cost(["wh-1"], claims=sm) is True
    assert omit_stock_count_variance_cost(["wh-1"], claims=admin) is False
    assert omit_bi_cost_fields(["store-1"], claims=sm) is True
    assert omit_bi_cost_fields(["store-1"], claims=acct) is False
    # Legacy fallback when claims omitted
    assert omit_inventory_report_cost(["wh-1"]) is True
    assert omit_inventory_report_cost(None) is False
    assert omit_bi_cost_fields(["store-1"]) is True
    assert omit_bi_cost_fields(None) is False


@pytest.mark.asyncio
async def test_broadened_export_gates_deny_cashier_allow_store_manager(client, db_session):
    """Commerce/dashboard/ops CSV paths require module:export (not mere read)."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    existing = (
        await db_session.execute(
            select(m.Store).where(m.Store.tenant_id == tid, m.Store.manager_id == mgr.id)
        )
    ).scalars().first()
    if existing is None:
        db_session.add(
            m.Store(
                tenant_id=tid,
                company_id=cid,
                code="MGR-EXP2",
                name="Mgr Export Store",
                manager_id=mgr.id,
                is_active=True,
            )
        )
        await db_session.commit()

    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    mgr_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    deny_paths = [
        ("/api/v1/dashboard/export", "dashboard:export"),
        ("/api/v1/expenses/export", "expenses:export"),
        ("/api/v1/inventory/movements/export", "inventory:export"),
        ("/api/v1/sales/orders/export", "sales:export"),
        ("/api/v1/credit/aging/export?kind=receivable", "credit:export"),
        ("/api/v1/ai/inventory/dead-stock/export", "ai:export"),
    ]
    for path, token in deny_paths:
        res = await ac.get(path, headers=cash)
        assert res.status_code == 403, f"{path}: {res.text}"
        assert token in res.text, f"{path}: expected {token} in {res.text}"

    allow_paths = [
        "/api/v1/dashboard/export",
        "/api/v1/expenses/export",
        "/api/v1/inventory/movements/export",
        "/api/v1/sales/orders/export",
        "/api/v1/credit/aging/export?kind=receivable",
        "/api/v1/stores/transfers/export",
    ]
    for path in allow_paths:
        res = await ac.get(path, headers=mgr_h)
        assert res.status_code == 200, f"{path}: {res.text}"
        assert "text/csv" in res.headers.get("content-type", ""), path


@pytest.mark.asyncio
async def test_inventory_balance_report_cost_redacted_for_store_manager(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = m.Product(
        tenant_id=tid,
        company_id=cid,
        sku="BAL-COST-1",
        name="Balance Cost Probe",
        selling_price=30,
        cost_price=11.25,
        stock_qty=5,
        is_active=True,
    )
    store = (
        await db_session.execute(
            select(m.Store).where(m.Store.tenant_id == tid, m.Store.manager_id == mgr.id)
        )
    ).scalars().first()
    if store is None:
        store = m.Store(
            tenant_id=tid,
            company_id=cid,
            code="MGR-BAL",
            name="Mgr Balance Store",
            manager_id=mgr.id,
            is_active=True,
        )
        db_session.add(store)
        await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        code="MGR-BAL-WH",
        name="Mgr Balance WH",
        is_active=True,
    )
    db_session.add_all([product, wh])
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh.id,
            product_id=product.id,
            quantity=5,
        )
    )
    await db_session.commit()

    mgr_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    res = await ac.get("/api/v1/reports/inventory/balance", headers=mgr_h)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data.get("total_value") is None
    items = data.get("items") or []
    probe = next((r for r in items if r.get("sku") == "BAL-COST-1"), None)
    assert probe is not None
    assert probe.get("cost_price") is None
    assert probe.get("value") is None

    admin_h = await _super(ac, seed)
    admin = await ac.get("/api/v1/reports/inventory/balance", headers=admin_h)
    assert admin.status_code == 200, admin.text
    adata = admin.json()["data"]
    aprobe = next(r for r in adata.get("items") or [] if r.get("sku") == "BAL-COST-1")
    assert float(aprobe.get("cost_price") or 0) == pytest.approx(11.25)
