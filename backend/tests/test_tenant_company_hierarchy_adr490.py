"""ADR-490 — Tenant/Company workspace isolation and subscription limits."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from tests.conftest import auth_headers


async def _super_headers(ac, seed) -> dict:
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tenant_workspace_blocks_pos_and_products(client):
    """Explicit tenant workspace cannot call company operational APIs."""
    ac, seed = client
    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"

    pos = await ac.get("/api/v1/pos/sessions", headers=headers)
    assert pos.status_code == 403
    assert pos.json()["detail"]["code"] == "COMPANY_WORKSPACE_REQUIRED"

    products = await ac.get("/api/v1/products", headers=headers)
    assert products.status_code == 403
    assert products.json()["detail"]["code"] == "COMPANY_WORKSPACE_REQUIRED"

    sales = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert sales.status_code == 403
    assert sales.json()["detail"]["code"] == "COMPANY_WORKSPACE_REQUIRED"


@pytest.mark.asyncio
async def test_company_workspace_allows_products_after_switch(client):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code == 200, r.text
    names = {p["name"] for p in r.json()["data"]}
    assert "Alpha Widget" in names
    assert "Beta Widget" not in names


@pytest.mark.asyncio
async def test_foreign_company_id_denied(client):
    """Changing X-Company-ID to another tenant's company must not leak data."""
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c2"].id

    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_same_tenant_second_company_isolation(client, db_session):
    """Company A membership cannot read Company B products in the same tenant."""
    ac, seed = client
    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="PHARM",
        name="Alpha Pharmacy",
        industry="pharmacy",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.Product(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            name="Pharmacy Only SKU",
            sku="P-ONLY",
            cost_price=1,
            selling_price=2,
            stock_qty=5,
        )
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = c_b.id
    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "COMPANY_MEMBERSHIP_REQUIRED"


@pytest.mark.asyncio
async def test_company_limit_blocks_fourth_company(client, db_session):
    ac, seed = client
    seed["t1"].plan_code = "business"
    seed["t1"].max_companies = 3
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"

    for i in range(2):
        r = await ac.post(
            "/api/v1/companies",
            headers=headers,
            json={"name": f"Extra Co {i}", "code": f"EX{i}", "industry": "retail"},
        )
        assert r.status_code in (200, 201), r.text

    r = await ac.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Over Limit", "code": "OVER", "industry": "retail"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "COMPANY_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_workspace_endpoint_lists_memberships(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/workspace", headers=headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["tenant_id"] == seed["t1"].id
    assert any(c["id"] == seed["c1"].id for c in body["companies"])
    assert all(c["id"] != seed["c2"].id for c in body["companies"])


@pytest.mark.asyncio
async def test_me_includes_workspace_fields(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/me", headers=headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["workspace_kind"] in ("tenant", "company")
    assert "company_memberships" in body
    assert body["company_id"] == seed["c1"].id or body["workspace_kind"] == "tenant"


@pytest.mark.asyncio
async def test_tenant_owner_permissions_are_account_scoped():
    perms = permissions_for_role("tenant_owner")
    assert "write" in perms.get("companies", [])
    assert "read" in perms.get("tenant_dashboard", [])
    assert "pos" not in perms
    assert "sales" not in perms
    assert "accounting" not in perms


@pytest.mark.asyncio
async def test_context_switch_changes_effective_access(client):
    """Same user: tenant workspace blocked from POS; company workspace allowed."""
    ac, seed = client
    headers = await _super_headers(ac, seed)

    tenant_h = {**headers, "X-Workspace-Kind": "tenant"}
    blocked = await ac.get("/api/v1/pos/sessions", headers=tenant_h)
    assert blocked.status_code == 403

    company_h = {
        **headers,
        "X-Workspace-Kind": "company",
        "X-Company-ID": seed["c1"].id,
    }
    allowed = await ac.get("/api/v1/products", headers=company_h)
    assert allowed.status_code == 200
