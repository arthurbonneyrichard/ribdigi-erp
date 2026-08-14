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


@pytest.mark.asyncio
async def test_customers_and_expenses_are_company_scoped(client, db_session):
    """Same-tenant second company customers/expenses must not leak into company A."""
    ac, seed = client
    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="REST",
        name="Alpha Restaurant",
        industry="restaurant",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    supplier_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="supplier",
        name="Restaurant Supplier",
        status="active",
        credit_limit=0,
    )
    customer_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="Restaurant Only Customer",
        status="active",
        credit_limit=0,
    )
    db_session.add_all([supplier_b, customer_b])
    await db_session.flush()
    db_session.add_all(
        [
            m.Expense(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                category="Ops",
                description="Restaurant kitchen expense",
                amount=42,
                status="approved",
                created_by=seed["super"].id,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                invoice_number="INV-REST-1",
                customer_id=customer_b.id,
                status="draft",
                subtotal=10,
                tax_amount=0,
                total_amount=10,
            ),
            m.PurchaseOrder(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                po_number="PO-REST-1",
                supplier_id=supplier_b.id,
                status="draft",
                subtotal=5,
                tax_amount=0,
                total_amount=5,
                created_by=seed["super"].id,
            ),
        ]
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    customers = await ac.get("/api/v1/customers", headers=headers)
    assert customers.status_code == 200, customers.text
    names = {r["name"] for r in customers.json()["data"]}
    assert "Restaurant Only Customer" not in names

    expenses = await ac.get("/api/v1/expenses", headers=headers)
    assert expenses.status_code == 200, expenses.text
    descs = {r.get("description") for r in expenses.json()["data"]}
    assert "Restaurant kitchen expense" not in descs

    invoices = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert invoices.status_code == 200, invoices.text
    inv_nums = {r.get("invoice_number") for r in invoices.json()["data"]}
    assert "INV-REST-1" not in inv_nums

    pos = await ac.get("/api/v1/purchasing/orders", headers=headers)
    assert pos.status_code == 200, pos.text
    po_nums = {r.get("po_number") for r in pos.json()["data"]}
    assert "PO-REST-1" not in po_nums


@pytest.mark.asyncio
async def test_finance_list_blocked_in_tenant_workspace(client):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"
    for path in (
        "/api/v1/expenses",
        "/api/v1/accounting/accounts",
        "/api/v1/accounting/journal-entries",
        "/api/v1/customers",
        "/api/v1/purchasing/orders",
    ):
        r = await ac.get(path, headers=headers)
        assert r.status_code == 403, path
        assert r.json()["detail"]["code"] == "COMPANY_WORKSPACE_REQUIRED"
