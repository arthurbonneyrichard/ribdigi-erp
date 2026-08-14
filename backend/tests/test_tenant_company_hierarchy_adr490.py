"""ADR-490 — Tenant/Company workspace isolation and subscription limits."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app import barcodes as barcode_svc
from app.rbac import permissions_for_role
from sqlalchemy import select
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


@pytest.mark.asyncio
async def test_docs_stock_lists_company_scoped(client, db_session):
    """Quotations and stock transfers from company B must not appear in company A lists."""
    ac, seed = client
    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="ELEC",
        name="Alpha Electronics",
        industry="electronics",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    cust = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="Electronics Customer",
        status="active",
        credit_limit=0,
    )
    db_session.add(cust)
    await db_session.flush()
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Electronics WH",
        code="WH-ELEC",
        is_active=True,
    )
    db_session.add(wh_b)
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesQuotation(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                quotation_number="Q-ELEC-1",
                customer_id=cust.id,
                status="draft",
                subtotal=10,
                tax_amount=0,
                total_amount=10,
                created_by=seed["super"].id,
            ),
            m.StockTransfer(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                transfer_number="TR-ELEC-1",
                from_warehouse_id=wh_b.id,
                to_warehouse_id=wh_b.id,
                status="draft",
                created_by=seed["super"].id,
            ),
            m.StockCount(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                count_number="SC-ELEC-1",
                status="draft",
                warehouse_id=wh_b.id,
                created_by=seed["super"].id,
            ),
            m.StockMovement(
                tenant_id=seed["t1"].id,
                company_id=c_b.id,
                product_id=seed["p1"].id,
                movement_type="adjustment",
                quantity=1,
                quantity_before=0,
                quantity_after=1,
                notes="elec-only-move",
                created_by=seed["super"].id,
            ),
        ]
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    quotes = await ac.get("/api/v1/sales/quotations", headers=headers)
    assert quotes.status_code == 200, quotes.text
    assert all(r.get("quotation_number") != "Q-ELEC-1" for r in quotes.json()["data"])

    transfers = await ac.get("/api/v1/inventory/stock-transfers", headers=headers)
    assert transfers.status_code == 200, transfers.text
    assert all(r.get("transfer_number") != "TR-ELEC-1" for r in transfers.json()["data"])

    counts = await ac.get("/api/v1/inventory/stock-counts", headers=headers)
    assert counts.status_code == 200, counts.text
    assert all(r.get("count_number") != "SC-ELEC-1" for r in counts.json()["data"])

    moves = await ac.get("/api/v1/inventory/movements", headers=headers)
    assert moves.status_code == 200, moves.text
    assert not any(r.get("notes") == "elec-only-move" for r in moves.json()["data"])


@pytest.mark.asyncio
async def test_journal_and_recurring_stamp_and_isolate(client, db_session):
    """Journal/recurring creates stamp company_id; company B rows stay out of company A lists."""
    ac, seed = client
    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="FINB",
        name="Alpha Finance B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.JournalEntry(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            entry_number="JE-FINB-1",
            description="Company B only journal",
            total_debit=10,
            total_credit=10,
            status="posted",
            created_by=seed["super"].id,
        )
    )
    db_session.add(
        m.RecurringExpense(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            category="Rent",
            description="Company B rent",
            amount=100,
            frequency="monthly",
            payment_method="bank_transfer",
            is_active=True,
            created_by=seed["super"].id,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    # Ensure default COA exists for company A, then post a balanced journal.
    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text
    codes = {a["code"]: a["id"] for a in accounts.json()["data"]}
    assert "1000" in codes and "4000" in codes

    posted = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Company A journal",
            "lines": [
                {"account_id": codes["1000"], "debit": 5, "credit": 0},
                {"account_id": codes["4000"], "debit": 0, "credit": 5},
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["description"] == "Company A journal"

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert journals.status_code == 200, journals.text
    descs = {r.get("description") for r in journals.json()["data"]}
    assert "Company A journal" in descs
    assert "Company B only journal" not in descs

    recurring = await ac.get("/api/v1/expenses/recurring", headers=headers)
    assert recurring.status_code == 200, recurring.text
    assert all(r.get("description") != "Company B rent" for r in recurring.json()["data"])

    create_rec = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "amount": 25,
            "frequency": "monthly",
            "description": "Company A utilities",
            "category": "Utilities",
        },
    )
    assert create_rec.status_code == 200, create_rec.text
    assert create_rec.json()["data"]["company_id"] == seed["c1"].id


@pytest.mark.asyncio
async def test_reports_sales_daily_company_scoped(client, db_session):
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="RPTB",
        name="Alpha Report B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="Report B Customer",
        status="active",
        credit_limit=0,
    )
    db_session.add(cust_b)
    await db_session.flush()
    now = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            invoice_number="INV-RPTB-1",
            customer_id=cust_b.id,
            status="posted",
            subtotal=999,
            tax_amount=0,
            total_amount=999,
            posted_at=now,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    r = await ac.get("/api/v1/reports/sales/daily", headers=headers)
    assert r.status_code == 200, r.text
    assert float(r.json()["data"]["total_revenue"] or 0) < 999


@pytest.mark.asyncio
async def test_company_membership_assign_and_revoke(client, db_session):
    ac, seed = client
    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="MEMB",
        name="Alpha Membership Co",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"

    listed = await ac.get(f"/api/v1/companies/{c_b.id}/memberships", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"] == []

    assigned = await ac.post(
        f"/api/v1/companies/{c_b.id}/memberships",
        headers=headers,
        json={"user_id": seed["u1"].id, "role": "cashier"},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["data"]["user_id"] == seed["u1"].id
    assert assigned.json()["data"]["is_active"] is True

    listed2 = await ac.get(f"/api/v1/companies/{c_b.id}/memberships", headers=headers)
    assert listed2.status_code == 200
    assert any(r["user_id"] == seed["u1"].id for r in listed2.json()["data"])

    revoked = await ac.delete(
        f"/api/v1/companies/{c_b.id}/memberships/{seed['u1'].id}",
        headers=headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_credit_aging_and_monthly_sales_company_scoped(client, db_session):
    """Company B AR / monthly sales must not inflate company A reports."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="CRDT",
        name="Alpha Credit B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="Credit B Customer",
        status="active",
        credit_limit=0,
        balance=500,
    )
    db_session.add(cust_b)
    await db_session.flush()
    now = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            invoice_number="INV-CRDT-1",
            customer_id=cust_b.id,
            status="posted",
            subtotal=500,
            tax_amount=0,
            total_amount=500,
            paid_amount=0,
            posted_at=now,
            due_date=now,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    aging = await ac.get("/api/v1/credit/aging", headers=headers)
    assert aging.status_code == 200, aging.text
    parties = {p.get("name") for p in aging.json()["data"].get("parties") or []}
    assert "Credit B Customer" not in parties
    assert float(aging.json()["data"].get("total_due") or 0) < 500

    monthly = await ac.get("/api/v1/reports/sales/monthly", headers=headers)
    assert monthly.status_code == 200, monthly.text
    assert float(monthly.json()["data"].get("total_revenue") or 0) < 500

    customers_csv = await ac.get("/api/v1/customers/export", headers=headers)
    assert customers_csv.status_code == 200, customers_csv.text
    assert "Credit B Customer" not in customers_csv.text


@pytest.mark.asyncio
async def test_trial_balance_and_payments_company_scoped(client, db_session):
    """Company B journals/payments must not appear in company A statements/registers."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="ACCT",
        name="Alpha Acct B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    acct_b = m.Account(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="9999",
        name="Company B Only Asset",
        account_type="asset",
        balance=777,
        is_active=True,
        is_system=False,
    )
    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="Pay B Customer",
        status="active",
        credit_limit=0,
    )
    db_session.add_all([acct_b, cust_b])
    await db_session.flush()
    db_session.add(
        m.CustomerPayment(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            payment_number="RCP-B-ONLY",
            customer_id=cust_b.id,
            amount=50,
            payment_method="cash",
            created_by=seed["super"].id,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    tb = await ac.get("/api/v1/accounting/trial-balance", headers=headers)
    assert tb.status_code == 200, tb.text
    codes = {r.get("code") for r in tb.json()["data"].get("rows") or []}
    assert "9999" not in codes

    payments = await ac.get("/api/v1/credit/customer-payments", headers=headers)
    assert payments.status_code == 200, payments.text
    nums = {r.get("payment_number") for r in payments.json()["data"]}
    assert "RCP-B-ONLY" not in nums

    pnl = await ac.get("/api/v1/accounting/profit-loss", headers=headers)
    assert pnl.status_code == 200, pnl.text


@pytest.mark.asyncio
async def test_outstanding_statements_and_liquid_company_scoped(client, db_session):
    """Company B outstanding/statement lines and liquid/bank rows stay out of company A."""
    ac, seed = client
    from datetime import datetime, timedelta

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="STMT",
        name="Alpha Stmt B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="Stmt B Customer",
        status="active",
        credit_limit=0,
        balance=250,
    )
    acct_b = m.Account(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="LIQB",
        name="Company B Liquid",
        account_type="asset",
        balance=100,
        is_cash_account=True,
        is_bank_account=False,
        is_active=True,
        is_system=False,
    )
    db_session.add_all([cust_b, acct_b])
    await db_session.flush()
    inv_b = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        invoice_number="INV-B-STMT",
        customer_id=cust_b.id,
        status="posted",
        total_amount=250,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=7),
        created_by=seed["super"].id,
    )
    db_session.add(inv_b)
    await db_session.flush()
    db_session.add(
        m.BankStatement(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            account_id=acct_b.id,
            statement_date=datetime.utcnow(),
            opening_balance=0,
            closing_balance=100,
            status="draft",
            notes="Company B only",
            created_by=seed["super"].id,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    outstanding = await ac.get(
        f"/api/v1/customers/{cust_b.id}/outstanding", headers=headers
    )
    assert outstanding.status_code == 404

    statement = await ac.get(
        f"/api/v1/credit/customers/{cust_b.id}/statement", headers=headers
    )
    assert statement.status_code == 404

    liquids = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert liquids.status_code == 200, liquids.text
    codes = {r.get("code") for r in liquids.json()["data"]}
    assert "LIQB" not in codes

    banks = await ac.get("/api/v1/accounting/bank-statements", headers=headers)
    assert banks.status_code == 200, banks.text
    notes = {r.get("notes") for r in banks.json()["data"]}
    assert "Company B only" not in notes

    create_liq = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={"kind": "cash", "code": "LIQA7", "name": "Company A Phase7 Cash"},
    )
    assert create_liq.status_code == 200, create_liq.text
    assert create_liq.json()["data"]["code"] == "LIQA7"


@pytest.mark.asyncio
async def test_bank_connections_and_cheques_company_scoped(client, db_session):
    """Company B bank connections and cheques must not appear in company A lists."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="BANK8",
        name="Alpha Bank B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    acct_b = m.Account(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="1010B",
        name="Company B Bank",
        account_type="asset",
        balance=0,
        is_cash_account=False,
        is_bank_account=True,
        is_active=True,
        is_system=False,
        bank_name="Beta Bank",
    )
    db_session.add(acct_b)
    await db_session.flush()
    db_session.add(
        m.BankAccountConnection(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            account_id=acct_b.id,
            provider="mock",
            display_name="Company B Feed",
            is_active=True,
            auto_sync=False,
        )
    )
    db_session.add(
        m.Cheque(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            direction="received",
            status="pending",
            cheque_number="CHQ-B-ONLY",
            amount=75,
            bank_name="Beta Bank",
            created_by=seed["super"].id,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    conns = await ac.get("/api/v1/accounting/bank-connections", headers=headers)
    assert conns.status_code == 200, conns.text
    names = {r.get("display_name") for r in conns.json()["data"]}
    assert "Company B Feed" not in names

    cheques = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert cheques.status_code == 200, cheques.text
    nums = {r.get("cheque_number") for r in cheques.json()["data"]}
    assert "CHQ-B-ONLY" not in nums

    foreign = await ac.get(
        f"/api/v1/accounting/accounts/{acct_b.id}", headers=headers
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_pos_sessions_sales_holds_and_lookup_company_scoped(client, db_session):
    """Company B POS sessions/sales/holds/catalog must not leak into company A."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="POS9",
        name="Alpha POS B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="POS B Only Widget",
        sku="POS-B-SKU",
        barcode="POSB0001",
        selling_price=10,
        stock_qty=5,
        is_active=True,
    )
    db_session.add(prod_b)
    await db_session.flush()
    sess_b = m.PosSession(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        user_id=seed["super"].id,
        session_number="POS-B-ONLY",
        status="open",
        opening_cash=0,
        expected_cash=0,
        opened_at=datetime.utcnow(),
    )
    db_session.add(sess_b)
    await db_session.flush()
    db_session.add(
        m.Transaction(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            tx_type="pos_sale",
            reference="POS_SALE-B-ONLY",
            session_id=sess_b.id,
            subtotal=10,
            tax=0,
            total=10,
            status="posted",
            payload={"payment_method": "cash"},
        )
    )
    db_session.add(
        m.PosHeldCart(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            user_id=seed["super"].id,
            session_id=sess_b.id,
            label="Company B Hold",
            cart_payload={"items": [{"product_id": prod_b.id, "quantity": 1}]},
            status="held",
            held_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    sessions = await ac.get("/api/v1/pos/sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    nums = {r.get("session_number") for r in sessions.json()["data"]}
    assert "POS-B-ONLY" not in nums

    sales = await ac.get("/api/v1/pos/sales", headers=headers)
    assert sales.status_code == 200, sales.text
    refs = {r.get("reference") for r in sales.json()["data"]}
    assert "POS_SALE-B-ONLY" not in refs

    holds = await ac.get("/api/v1/pos/holds", headers=headers)
    assert holds.status_code == 200, holds.text
    labels = {r.get("label") for r in holds.json()["data"]}
    assert "Company B Hold" not in labels

    lookup = await ac.get(
        "/api/v1/pos/products/search",
        headers=headers,
        params={"q": "POS-B-SKU"},
    )
    assert lookup.status_code == 200, lookup.text
    skus = {r.get("sku") for r in lookup.json()["data"]}
    assert "POS-B-SKU" not in skus

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["company_id"] == seed["c1"].id
    sessions2 = await ac.get("/api/v1/pos/sessions?status=open", headers=headers)
    assert sessions2.status_code == 200
    open_nums = {r.get("session_number") for r in sessions2.json()["data"]}
    assert "POS-B-ONLY" not in open_nums
    assert opened.json()["data"]["session_number"] in open_nums


@pytest.mark.asyncio
async def test_tax_rates_and_reports_company_scoped(client, db_session):
    """Company B tax rates and tax report rows must not leak into company A."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="TAX10",
        name="Alpha Tax B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    party_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Tax B Customer",
        kind="customer",
        credit_limit=0,
    )
    db_session.add(party_b)
    await db_session.flush()
    rate_b = m.TaxRate(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Company B Only VAT",
        rate=7.5,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=True,
        is_active=True,
    )
    db_session.add(rate_b)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            customer_id=party_b.id,
            invoice_number="INV-TAX-B-ONLY",
            status="posted",
            subtotal=100,
            tax_amount=7.5,
            total_amount=107.5,
            posted_at=datetime.utcnow(),
        )
    )
    db_session.add(
        m.Transaction(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            tx_type="pos_sale",
            reference="POS-TAX-B-ONLY",
            subtotal=50,
            tax=3.75,
            total=53.75,
            status="posted",
            payload={"items": []},
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    listed = await ac.get("/api/v1/tax/rates", headers=headers)
    assert listed.status_code == 200, listed.text
    names = {r.get("name") for r in listed.json()["data"]}
    assert "Company B Only VAT" not in names

    foreign = await ac.get(f"/api/v1/tax/rates/{rate_b.id}", headers=headers)
    assert foreign.status_code == 404

    created = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "Company A Phase10 VAT",
            "rate": 12.5,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": False,
            "is_active": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["company_id"] == seed["c1"].id
    assert created.json()["data"]["name"] == "Company A Phase10 VAT"

    report = await ac.get("/api/v1/reports/tax", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    # Company B invoice/POS tax must not inflate company A output boxes.
    assert float(data.get("output_tax_invoices") or 0) != 7.5
    assert float(data.get("output_tax_pos") or 0) != 3.75
    assert float(data.get("output_tax_invoices") or 0) == 0.0
    assert float(data.get("output_tax_pos") or 0) == 0.0

    export = await ac.get("/api/v1/tax/rates/export", headers=headers)
    assert export.status_code == 200, export.text
    assert "Company B Only VAT" not in export.text
    assert "Company A Phase10 VAT" in export.text


@pytest.mark.asyncio
async def test_ai_ops_and_schedules_company_scoped(client, db_session):
    """Company B AI aggregations / notifications / schedules must not leak into company A."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="AI11",
        name="Alpha AI B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    party_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="AI B Customer",
        kind="customer",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="AI B Only SKU Widget",
        sku="AI-B-SKU",
        selling_price=25,
        stock_qty=2,
        reorder_level=10,
        is_active=True,
    )
    db_session.add_all([party_b, prod_b])
    await db_session.flush()
    inv_b = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        customer_id=party_b.id,
        invoice_number="INV-AI-B-ONLY",
        status="posted",
        subtotal=250,
        tax_amount=0,
        total_amount=250,
        posted_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db_session.add(inv_b)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            sales_invoice_id=inv_b.id,
            product_id=prod_b.id,
            quantity=10,
            unit_price=25,
            line_total=250,
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            category="AI B Expense",
            description="Company B only expense",
            amount=999.0,
            status="approved",
            expense_date=datetime.utcnow(),
        )
    )
    db_session.add(
        m.PurchaseOrder(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            po_number="PO-AI-B-ONLY",
            supplier_id=party_b.id,
            status="sent",
            subtotal=100,
            tax_amount=0,
            total_amount=100,
        )
    )
    db_session.add(
        m.Notification(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            user_id=seed["super"].id,
            category="ai_insight",
            title="Company B AI Alert",
            message="Should not appear in company A",
            status="unread",
        )
    )
    db_session.add(
        m.ReportSchedule(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            name="Company B Only Schedule",
            report_type="sales_daily",
            format="csv",
            frequency="daily",
            hour_utc=6,
            recipients=["ops-b@example.com"],
            enabled=True,
            created_by=seed["super"].id,
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    sales = await ac.get("/api/v1/ai/sales/analysis", headers=headers)
    assert sales.status_code == 200, sales.text
    sales_blob = sales.text
    assert "INV-AI-B-ONLY" not in sales_blob
    assert float(sales.json()["data"].get("total_sales") or 0) != 250.0

    low = await ac.get("/api/v1/ai/inventory/low-stock-prediction", headers=headers)
    assert low.status_code == 200, low.text
    skus = {r.get("sku") for r in low.json()["data"].get("predictions") or []}
    assert "AI-B-SKU" not in skus

    expenses = await ac.get("/api/v1/ai/expenses/analysis", headers=headers)
    assert expenses.status_code == 200, expenses.text
    assert "Company B only expense" not in expenses.text
    assert float(expenses.json()["data"].get("total_approved") or 0) != 999.0

    purchases = await ac.get("/api/v1/ai/purchases/analysis", headers=headers)
    assert purchases.status_code == 200, purchases.text
    assert "PO-AI-B-ONLY" not in purchases.text

    insights = await ac.get("/api/v1/ai/insights", headers=headers)
    assert insights.status_code == 200, insights.text
    assert "AI-B-SKU" not in insights.text

    notes = await ac.get("/api/v1/notifications", headers=headers)
    assert notes.status_code == 200, notes.text
    titles = {n.get("title") for n in notes.json()["data"]}
    assert "Company B AI Alert" not in titles

    schedules = await ac.get("/api/v1/reports/schedules", headers=headers)
    assert schedules.status_code == 200, schedules.text
    names = {r.get("name") for r in schedules.json()["data"]}
    assert "Company B Only Schedule" not in names

    created = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={
            "name": "Company A Phase11 Schedule",
            "report_type": "sales_daily",
            "format": "csv",
            "frequency": "daily",
            "hour_utc": 7,
            "recipients": ["ops-a@example.com"],
            "enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["company_id"] == seed["c1"].id
    assert created.json()["data"]["name"] == "Company A Phase11 Schedule"


@pytest.mark.asyncio
async def test_ai_chat_templates_customers_company_scoped(client, db_session):
    """Company B chat history, templates, and customer insights must not leak into A."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="AI12",
        name="Alpha AI Chat B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    party_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="AI12 B Only Customer",
        kind="customer",
        status="active",
        credit_limit=0,
    )
    db_session.add(party_b)
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            customer_id=party_b.id,
            invoice_number="INV-AI12-B-ONLY",
            status="posted",
            subtotal=400,
            tax_amount=0,
            total_amount=400,
            posted_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
    )
    db_session.add(
        m.AiQuery(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            user_id=seed["super"].id,
            role="super_admin",
            message="secret company B chat",
            answer="Company B only answer marker AI12-B-CHAT",
            intent="help",
        )
    )
    db_session.add(
        m.AiReportTemplate(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            user_id=seed["super"].id,
            name="Company B Only Template AI12",
            prompt="Show me sales daily",
            report_type="sales_daily",
            format="csv",
            params={},
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    history = await ac.get("/api/v1/ai/chat/history", headers=headers)
    assert history.status_code == 200, history.text
    blob = history.text
    assert "AI12-B-CHAT" not in blob
    assert "secret company B chat" not in blob

    templates = await ac.get("/api/v1/ai/reports/templates", headers=headers)
    assert templates.status_code == 200, templates.text
    names = {r.get("name") for r in templates.json()["data"]}
    assert "Company B Only Template AI12" not in names

    created_tmpl = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={
            "name": "Company A Phase12 Template",
            "prompt": "Show me sales daily",
            "format": "csv",
        },
    )
    assert created_tmpl.status_code == 200, created_tmpl.text
    assert created_tmpl.json()["data"]["company_id"] == seed["c1"].id

    chat = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "How many customers do I have?"},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["data"].get("company_id") == seed["c1"].id
    # History should now include company A stamped turn and still exclude B
    history2 = await ac.get("/api/v1/ai/chat/history", headers=headers)
    assert history2.status_code == 200
    assert "AI12-B-CHAT" not in history2.text
    items = history2.json()["data"].get("items") or []
    assert any("customers" in (i.get("message") or "").lower() for i in items)

    insights = await ac.get("/api/v1/ai/customers/insights", headers=headers)
    assert insights.status_code == 200, insights.text
    assert "AI12 B Only Customer" not in insights.text
    names_c = {
        c.get("name") for c in (insights.json()["data"].get("best_customers") or [])
    }
    assert "AI12 B Only Customer" not in names_c


@pytest.mark.asyncio
async def test_dashboard_catalog_meta_alerts_company_scoped(client, db_session):
    """Phase 13: dashboard slices, catalog/expense/group meta, and low-stock stay company-scoped."""
    ac, seed = client
    from datetime import datetime

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="META13",
        name="Alpha Meta B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    party_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Meta B Customer",
        kind="customer",
        status="active",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Meta B Low Stock Widget",
        sku="META-B-LOW",
        selling_price=10,
        stock_qty=1,
        reorder_level=20,
        is_active=True,
    )
    cat_b = m.ProductCategory(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="METAB",
        name="Company B Only Category",
        is_active=True,
    )
    exp_cat_b = m.ExpenseCategory(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="BONLY",
        name="Company B Only Expense Cat",
        is_active=True,
    )
    group_b = m.CustomerGroup(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Company B Only Group",
        is_active=True,
    )
    store_b = m.Store(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="STOREB13",
        name="Company B Only Store",
        is_active=True,
    )
    db_session.add_all([party_b, prod_b, cat_b, exp_cat_b, group_b, store_b])
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            customer_id=party_b.id,
            invoice_number="INV-META13-B",
            status="posted",
            subtotal=500,
            tax_amount=0,
            total_amount=500,
            posted_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            category_id=exp_cat_b.id,
            category="Company B Only Expense Cat",
            description="Meta B expense",
            amount=777.0,
            status="approved",
            expense_date=datetime.utcnow(),
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    summary = await ac.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert "META-B-LOW" not in summary.text
    assert "Meta B Low Stock Widget" not in summary.text

    top = await ac.get("/api/v1/dashboard/top-products", headers=headers)
    assert top.status_code == 200, top.text
    assert "META-B-LOW" not in top.text

    stock = await ac.get("/api/v1/dashboard/stock-alerts", headers=headers)
    assert stock.status_code == 200, stock.text
    assert "META-B-LOW" not in stock.text

    cats = await ac.get("/api/v1/catalog/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_names = {r.get("name") for r in cats.json()["data"]}
    assert "Company B Only Category" not in cat_names

    created_cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "META13A", "name": "Company A Phase13 Category"},
    )
    assert created_cat.status_code == 200, created_cat.text
    assert created_cat.json()["data"]["company_id"] == seed["c1"].id

    exp_cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert exp_cats.status_code == 200, exp_cats.text
    exp_names = {r.get("name") for r in exp_cats.json()["data"]}
    assert "Company B Only Expense Cat" not in exp_names

    groups = await ac.get("/api/v1/customers/groups", headers=headers)
    assert groups.status_code == 200, groups.text
    group_names = {r.get("name") for r in groups.json()["data"]}
    assert "Company B Only Group" not in group_names

    created_group = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "Company A Phase13 Group"},
    )
    assert created_group.status_code == 200, created_group.text
    assert created_group.json()["data"]["company_id"] == seed["c1"].id

    low = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    assert "META-B-LOW" not in low.text

    stores_export = await ac.get("/api/v1/stores/export", headers=headers)
    assert stores_export.status_code == 200, stores_export.text
    assert "Company B Only Store" not in stores_export.text
    assert "STOREB13" not in stores_export.text

    foreign_store = await ac.patch(
        f"/api/v1/stores/{store_b.id}",
        headers=headers,
        json={"name": "Hijack Store B"},
    )
    assert foreign_store.status_code == 404


@pytest.mark.asyncio
async def test_audit_org_units_backup_company_scoped(client, db_session, tmp_path, monkeypatch):
    """Phase 14: audit/org-unit company isolation; backup requires tenant workspace."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="ORG14",
        name="Alpha Org B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    branch_b = m.Branch(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="BRB14",
        name="Company B Only Branch",
        is_active=True,
    )
    dept_b = m.Department(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="DEPB14",
        name="Company B Only Dept",
        is_active=True,
    )
    db_session.add_all([branch_b, dept_b])
    db_session.add(
        m.AuditLog(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            user_id=seed["u1"].id,
            module="sales",
            action="secret_b",
            entity="invoice",
            entity_id=None,
            details={"note": "company-b-only"},
        )
    )
    db_session.add(
        m.AuditLog(
            tenant_id=seed["t1"].id,
            company_id=None,
            user_id=seed["u1"].id,
            module="security",
            action="login_failed",
            entity="auth",
            entity_id=None,
            details={"note": "null-company-auth"},
        )
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id

    # Company workspace cannot dump backups.
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))
    denied_backup = await ac.get("/api/v1/backup", headers=headers)
    assert denied_backup.status_code == 403
    assert denied_backup.json()["detail"]["code"] == "TENANT_WORKSPACE_REQUIRED"

    audits = await ac.get("/api/v1/audit-logs", headers=headers)
    assert audits.status_code == 200, audits.text
    actions = {r.get("action") for r in audits.json()["data"]}
    assert "secret_b" not in actions
    assert "login_failed" in actions

    branches = await ac.get("/api/v1/branches", headers=headers)
    assert branches.status_code == 200, branches.text
    branch_names = {r.get("name") for r in branches.json()["data"]}
    assert "Company B Only Branch" not in branch_names

    created_branch = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "BRA14", "name": "Company A Phase14 Branch"},
    )
    assert created_branch.status_code == 200, created_branch.text
    assert created_branch.json()["data"]["company_id"] == seed["c1"].id

    depts = await ac.get("/api/v1/departments", headers=headers)
    assert depts.status_code == 200, depts.text
    dept_names = {r.get("name") for r in depts.json()["data"]}
    assert "Company B Only Dept" not in dept_names

    created_dept = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "DEPA14", "name": "Company A Phase14 Dept"},
    )
    assert created_dept.status_code == 200, created_dept.text
    assert created_dept.json()["data"]["company_id"] == seed["c1"].id

    foreign_branch = await ac.patch(
        f"/api/v1/branches/{branch_b.id}",
        headers=headers,
        json={"name": "Hijack Branch B"},
    )
    assert foreign_branch.status_code == 404

    # Tenant workspace can list backups.
    tenant_h = await _super_headers(ac, seed)
    tenant_h["X-Workspace-Kind"] = "tenant"
    listed = await ac.get("/api/v1/backup", headers=tenant_h)
    assert listed.status_code == 200, listed.text


@pytest.mark.asyncio
async def test_company_scoped_uniques_and_product_idor(client, db_session):
    """Phase 15: company-scoped codes/SKUs; product/notification IDOR hardening."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="UQ15",
        name="Alpha Unique B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Company B Product",
        sku="SHARED-SKU-15",
        cost_price=1,
        selling_price=2,
        stock_qty=3,
        is_active=True,
    )
    note_b = m.Notification(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        user_id=seed["super"].id,
        title="Company B Only Note",
        message="secret",
        category="system",
        status="unread",
    )
    db_session.add_all([prod_b, note_b])
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    # Same branch/store/customer codes allowed in company A while B already has them via create path.
    branch_a = await ac.post(
        "/api/v1/branches",
        headers=headers_a,
        json={"code": "HQ15", "name": "Company A HQ"},
    )
    assert branch_a.status_code == 200, branch_a.text

    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id
    branch_b = await ac.post(
        "/api/v1/branches",
        headers=headers_b,
        json={"code": "HQ15", "name": "Company B HQ"},
    )
    assert branch_b.status_code == 200, branch_b.text

    store_a = await ac.post(
        "/api/v1/stores",
        headers=headers_a,
        json={"name": "Store A", "code": "MAIN15"},
    )
    assert store_a.status_code == 200, store_a.text
    store_b = await ac.post(
        "/api/v1/stores",
        headers=headers_b,
        json={"name": "Store B", "code": "MAIN15"},
    )
    assert store_b.status_code == 200, store_b.text

    cust_a = await ac.post(
        "/api/v1/customers",
        headers=headers_a,
        json={"name": "Cust A", "code": "C00115"},
    )
    assert cust_a.status_code == 200, cust_a.text
    cust_b = await ac.post(
        "/api/v1/customers",
        headers=headers_b,
        json={"name": "Cust B", "code": "C00115"},
    )
    assert cust_b.status_code == 200, cust_b.text

    # Product IDOR
    foreign = await ac.get(f"/api/v1/products/{prod_b.id}", headers=headers_a)
    assert foreign.status_code == 404
    hijack = await ac.patch(
        f"/api/v1/products/{prod_b.id}",
        headers=headers_a,
        json={"name": "Hijacked"},
    )
    assert hijack.status_code == 404

    # Variant SKU can match other company's product SKU within company A product.
    products = await ac.get("/api/v1/products", headers=headers_a)
    assert products.status_code == 200
    alpha = next(p for p in products.json()["data"] if p["name"] == "Alpha Widget")
    variant = await ac.post(
        f"/api/v1/products/{alpha['id']}/variants",
        headers=headers_a,
        json={"name": "Size L", "sku": "SHARED-SKU-15"},
    )
    assert variant.status_code == 200, variant.text
    assert variant.json()["data"]["company_id"] == seed["c1"].id

    # Notification mark-all in A does not clear B's note; foreign mark-read → 404
    mark_all = await ac.post("/api/v1/notifications/read-all", headers=headers_a)
    assert mark_all.status_code == 200, mark_all.text
    await db_session.refresh(note_b)
    assert note_b.status == "unread"

    foreign_note = await ac.patch(
        f"/api/v1/notifications/{note_b.id}/read",
        headers=headers_a,
    )
    assert foreign_note.status_code == 404

    # Cross-company branch assignment rejected
    bad_store = await ac.post(
        "/api/v1/stores",
        headers=headers_a,
        json={
            "name": "Bad Link",
            "code": "BAD15",
            "branch_id": branch_b.json()["data"]["id"],
        },
    )
    assert bad_store.status_code == 404


@pytest.mark.asyncio
async def test_document_numbering_and_nested_product_idor(client, db_session):
    """Phase 16: per-company doc series; nested product / stock-count IDOR."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="DOC16",
        name="Alpha Docs B",
        industry="retail",
        is_active=True,
        is_default=False,
        document_numbering={
            "sales_invoice": {"prefix": "BINV", "include_year": False, "pad": 4, "next_number": 1}
        },
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Docs B Product",
        sku="DOC16-B",
        cost_price=1,
        selling_price=2,
        stock_qty=5,
        is_active=True,
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Docs B Warehouse",
        code="WH-DOC16B",
        warehouse_type="retail",
        is_active=True,
    )
    db_session.add_all([prod_b, wh_b])
    await db_session.flush()
    count_b = m.StockCount(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        count_number="SC-B-16",
        status="draft",
        warehouse_id=wh_b.id,
    )
    db_session.add(count_b)
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    # Configure company A series without affecting B preview.
    patch_a = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers_a,
        json={
            "document_numbering": {
                "sales_invoice": {
                    "prefix": "AINV",
                    "include_year": False,
                    "pad": 4,
                    "next_number": 1,
                }
            }
        },
    )
    assert patch_a.status_code == 200, patch_a.text
    assert patch_a.json()["data"]["document_numbering_scope"] == "company"
    assert patch_a.json()["data"]["document_numbering"]["sales_invoice"]["prefix"] == "AINV"

    me_b = await ac.get("/api/v1/tenants/me", headers=headers_b)
    assert me_b.status_code == 200, me_b.text
    assert me_b.json()["data"]["document_numbering"]["sales_invoice"]["prefix"] == "BINV"

    # Independent invoice numbers per company.
    cust_a = await ac.post(
        "/api/v1/customers",
        headers=headers_a,
        json={"name": "Doc Cust A"},
    )
    assert cust_a.status_code == 200, cust_a.text
    inv_a = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers_a,
        json={
            "customer_id": cust_a.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert inv_a.status_code == 200, inv_a.text
    assert inv_a.json()["data"]["invoice_number"].startswith("AINV-")

    cust_b = await ac.post(
        "/api/v1/customers",
        headers=headers_b,
        json={"name": "Doc Cust B"},
    )
    assert cust_b.status_code == 200, cust_b.text
    # Need a product in company B for invoice lines
    prod_b_create = await ac.post(
        "/api/v1/products",
        headers=headers_b,
        json={"name": "Docs B Line Product", "sku": "DOC16-BL", "selling_price": 3, "cost_price": 1},
    )
    assert prod_b_create.status_code == 200, prod_b_create.text
    inv_b = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers_b,
        json={
            "customer_id": cust_b.json()["data"]["id"],
            "items": [
                {"product_id": prod_b_create.json()["data"]["id"], "quantity": 1, "unit_price": 3}
            ],
        },
    )
    assert inv_b.status_code == 200, inv_b.text
    assert inv_b.json()["data"]["invoice_number"].startswith("BINV-")
    # Same sequence start allowed across companies
    assert inv_a.json()["data"]["invoice_number"].endswith("0001")
    assert inv_b.json()["data"]["invoice_number"].endswith("0001")

    # Nested product IDOR
    assert (await ac.get(f"/api/v1/products/{prod_b.id}/images", headers=headers_a)).status_code == 404
    assert (await ac.get(f"/api/v1/products/{prod_b.id}/batches", headers=headers_a)).status_code == 404
    assert (
        await ac.get(f"/api/v1/products/{prod_b.id}/warehouse-stock", headers=headers_a)
    ).status_code == 404

    # Stock count IDOR
    assert (
        await ac.get(f"/api/v1/inventory/stock-counts/{count_b.id}", headers=headers_a)
    ).status_code == 404


@pytest.mark.asyncio
async def test_print_templates_and_search_history_company_scoped(client, db_session):
    """Phase 17: per-company print templates; search/history isolation."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="PRT17",
        name="Alpha Print B",
        industry="retail",
        is_active=True,
        is_default=False,
        invoice_print_template="thermal_58",
        receipt_print_template="thermal_58",
        document_header="Company B Header",
        document_footer="Company B Footer",
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Print B Unique Widget",
        sku="PRT17-B",
        cost_price=1,
        selling_price=2,
        stock_qty=5,
        is_active=True,
    )
    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Print B Unique Customer",
        kind="customer",
        credit_limit=0,
    )
    db_session.add_all([prod_b, cust_b])
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    patch_a = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers_a,
        json={
            "invoice_print_template": "a4",
            "receipt_print_template": "thermal_80",
            "document_header": "Company A Header",
            "document_footer": "Company A Footer",
        },
    )
    assert patch_a.status_code == 200, patch_a.text
    data_a = patch_a.json()["data"]
    assert data_a["print_templates_scope"] == "company"
    assert data_a["document_header"] == "Company A Header"
    assert data_a["invoice_print_template"] == "a4"

    me_b = await ac.get("/api/v1/tenants/me", headers=headers_b)
    assert me_b.status_code == 200, me_b.text
    data_b = me_b.json()["data"]
    assert data_b["document_header"] == "Company B Header"
    assert data_b["invoice_print_template"] == "thermal_58"

    preview_a = await ac.get(
        "/api/v1/tenants/me/print-templates/preview",
        headers=headers_a,
        params={"kind": "invoice", "format": "text"},
    )
    assert preview_a.status_code == 200, preview_a.text
    assert "Company A Header" in preview_a.text

    preview_b = await ac.get(
        "/api/v1/tenants/me/print-templates/preview",
        headers=headers_b,
        params={"kind": "invoice", "format": "text"},
    )
    assert preview_b.status_code == 200, preview_b.text
    assert "Company B Header" in preview_b.text

    search_a = await ac.get("/api/v1/search", headers=headers_a, params={"q": "Print B Unique"})
    assert search_a.status_code == 200, search_a.text
    assert search_a.json()["data"]["total"] == 0

    search_b = await ac.get("/api/v1/search", headers=headers_b, params={"q": "Print B Unique"})
    assert search_b.status_code == 200, search_b.text
    labels = {r["label"] for r in search_b.json()["data"]["results"]}
    assert "Print B Unique Widget" in labels or "Print B Unique Customer" in labels

    # History for company-A customer must not list sibling company docs if any shared id edge.
    hist = await ac.get(
        f"/api/v1/customers/{seed['party1'].id}/history",
        headers=headers_a,
    )
    assert hist.status_code == 200, hist.text
    assert "invoices" in hist.json()["data"]


@pytest.mark.asyncio
async def test_mutate_idor_exports_and_ops_numbers_company_scoped(client, db_session):
    """Phase 18: mutate IDOR, pipeline export scope, company-local session numbers."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="OPS18",
        name="Alpha Ops B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )
    party_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Ops B Customer",
        kind="customer",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Ops B Product",
        sku="OPS18-B",
        cost_price=1,
        selling_price=5,
        stock_qty=10,
        is_active=True,
    )
    db_session.add_all([party_b, prod_b])
    await db_session.flush()
    quote_b = m.SalesQuotation(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        quotation_number="QT-OPS18-B",
        customer_id=party_b.id,
        status="draft",
        subtotal=5,
        tax_amount=0,
        discount_amount=0,
        total_amount=5,
        created_by=seed["super"].id,
    )
    db_session.add(quote_b)
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    # Cross-company mutate IDOR
    send = await ac.post(
        f"/api/v1/sales/quotations/{quote_b.id}/send",
        headers=headers_a,
    )
    assert send.status_code == 404, send.text

    # Export from A must not include B quotation number
    export_a = await ac.get("/api/v1/sales/quotations/export", headers=headers_a)
    assert export_a.status_code == 200, export_a.text
    assert "QT-OPS18-B" not in export_a.text

    export_b = await ac.get("/api/v1/sales/quotations/export", headers=headers_b)
    assert export_b.status_code == 200, export_b.text
    assert "QT-OPS18-B" in export_b.text

    # Company-local POS session numbering
    open_a = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers_a,
        json={"opening_cash": 0},
    )
    assert open_a.status_code == 200, open_a.text
    assert open_a.json()["data"]["company_id"] == seed["c1"].id
    assert open_a.json()["data"]["session_number"].startswith("POS-")


@pytest.mark.asyncio
async def test_barcode_uniques_and_child_stamps_company_scoped(client, db_session):
    """Phase 20: company-scoped barcodes + child row company_id stamps."""
    ac, seed = client
    shared_barcode = barcode_svc.generate_ean13()

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="BC20",
        name="Alpha Barcode B",
        industry="bakery",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id
    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    # Same barcode allowed across companies
    create_a = await ac.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "Barcode A Product",
            "sku": "BC-A-1",
            "barcode": shared_barcode,
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
        },
    )
    assert create_a.status_code == 200, create_a.text
    prod_a_id = create_a.json()["data"]["id"]
    assert create_a.json()["data"]["barcode"] == shared_barcode

    create_b = await ac.post(
        "/api/v1/products",
        headers=headers_b,
        json={
            "name": "Barcode B Product",
            "sku": "BC-B-1",
            "barcode": shared_barcode,
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
        },
    )
    assert create_b.status_code == 200, create_b.text
    assert create_b.json()["data"]["barcode"] == shared_barcode

    # Clash within the same company
    clash = await ac.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "Barcode A Clash",
            "sku": "BC-A-2",
            "barcode": shared_barcode,
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
        },
    )
    assert clash.status_code == 409, clash.text

    # Generate barcode is company-scoped / IDOR-safe
    gen = await ac.post(
        f"/api/v1/products/{prod_a_id}/barcode/generate?force=true&format=code128",
        headers=headers_a,
    )
    assert gen.status_code == 200, gen.text
    assert gen.json()["data"]["barcode"]

    foreign_gen = await ac.post(
        f"/api/v1/products/{prod_a_id}/barcode/generate?force=true",
        headers=headers_b,
    )
    assert foreign_gen.status_code == 404, foreign_gen.text

    # Labels cannot resolve cross-company product
    labels = await ac.get(
        f"/api/v1/products/{prod_a_id}/labels",
        headers=headers_b,
    )
    assert labels.status_code == 404, labels.text

    # Child stamps: batch inbound stamps company_id
    batch_prod = await ac.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "Batch Stamp Product",
            "sku": "BC-BATCH-1",
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
            "tracks_batches": True,
        },
    )
    assert batch_prod.status_code == 200, batch_prod.text
    bp_id = batch_prod.json()["data"]["id"]

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers_a,
        json={
            "product_id": bp_id,
            "quantity": 5,
            "batch_number": "LOT-20",
            "notes": "phase20",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    batch_row = (
        await db_session.execute(
            select(m.ProductBatch).where(
                m.ProductBatch.product_id == bp_id,
                m.ProductBatch.batch_number == "LOT-20",
            )
        )
    ).scalar_one_or_none()
    assert batch_row is not None
    assert batch_row.company_id == seed["c1"].id

    supplier = m.Party(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="Alpha Supplier P20",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers_a,
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert pr.status_code == 200, pr.text
    pr_id = pr.json()["data"]["id"]
    pr_item = (
        await db_session.execute(
            select(m.PurchaseRequestItem).where(
                m.PurchaseRequestItem.purchase_request_id == pr_id
            )
        )
    ).scalar_one()
    assert pr_item.company_id == seed["c1"].id


@pytest.mark.asyncio
async def test_cheque_client_request_and_clearing_stamps_company_scoped(client, db_session):
    """Phase 21: company-scoped cheque/client_request_id uniques + clearing stamps."""
    from datetime import datetime

    from app import accounting as accounting_svc
    from app import bank_recon as recon
    from app import cheques as cheques_svc

    ac, seed = client
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="UQ21",
        name="Alpha Unique B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )
    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="Customer B P21",
        kind="customer",
        credit_limit=0,
        balance=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="POS B P21 Widget",
        sku="P21-B-SKU",
        cost_price=1,
        selling_price=10,
        stock_qty=20,
        tax_exempt=True,
        is_active=True,
    )
    db_session.add_all([cust_b, prod_b])
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id
    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    # --- Cheque numbers: same number OK across companies; clash within company ---
    shared_chq = "CHQ-P21-SHARED"

    async def _invoice_and_cheque(headers, customer_id, product_id, cheque_number):
        inv = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={
                "customer_id": customer_id,
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": 1,
                        "unit_price": 50,
                        "tax_rate": 0,
                    }
                ],
            },
        )
        assert inv.status_code == 200, inv.text
        invoice_id = inv.json()["data"]["id"]
        total = float(inv.json()["data"]["total_amount"])
        posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
        assert posted.status_code == 200, posted.text
        pay = await ac.post(
            "/api/v1/sales/payments",
            headers=headers,
            json={
                "customer_id": customer_id,
                "amount": total,
                "sales_invoice_id": invoice_id,
                "payment_method": "cheque",
                "reference": cheque_number,
                "cheque_number": cheque_number,
                "bank_name": "Test Bank",
            },
        )
        return pay

    pay_a = await _invoice_and_cheque(headers_a, seed["party1"].id, seed["p1"].id, shared_chq)
    assert pay_a.status_code == 200, pay_a.text
    pay_b = await _invoice_and_cheque(headers_b, cust_b.id, prod_b.id, shared_chq)
    assert pay_b.status_code == 200, pay_b.text

    # Second cheque in company A with same number must 409
    inv2 = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers_a,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 25,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv2.status_code == 200, inv2.text
    await ac.post(f"/api/v1/sales/invoices/{inv2.json()['data']['id']}/post", headers=headers_a)
    clash = await ac.post(
        "/api/v1/sales/payments",
        headers=headers_a,
        json={
            "customer_id": seed["party1"].id,
            "amount": float(inv2.json()["data"]["total_amount"]),
            "sales_invoice_id": inv2.json()["data"]["id"],
            "payment_method": "cheque",
            "reference": shared_chq,
            "cheque_number": shared_chq,
        },
    )
    assert clash.status_code == 409, clash.text

    listed = await cheques_svc.list_cheques(
        db_session, seed["t1"].id, direction="received", company_id=seed["c1"].id
    )
    assert any(c.cheque_number == shared_chq and c.company_id == seed["c1"].id for c in listed)

    # --- client_request_id: same key OK across companies; replay within company ---
    seed["p1"].selling_price = 10
    seed["p1"].stock_qty = 20
    seed["p1"].reserved_qty = 0
    seed["p1"].tax_exempt = True
    seed["p1"].tax_rate_id = None
    await db_session.commit()

    open_a = await ac.post(
        "/api/v1/pos/sessions/open", headers=headers_a, json={"opening_cash": 0}
    )
    assert open_a.status_code == 200, open_a.text
    open_b = await ac.post(
        "/api/v1/pos/sessions/open", headers=headers_b, json={"opening_cash": 0}
    )
    assert open_b.status_code == 200, open_b.text

    shared_key = "idem-p21-shared-key"
    body_a = {
        "session_id": open_a.json()["data"]["session_id"],
        "client_request_id": shared_key,
        "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        "payments": [{"payment_method": "cash", "amount": 10}],
    }
    body_b = {
        "session_id": open_b.json()["data"]["session_id"],
        "client_request_id": shared_key,
        "items": [{"product_id": prod_b.id, "quantity": 1}],
        "payments": [{"payment_method": "cash", "amount": 10}],
    }
    sale_a = await ac.post("/api/v1/pos/sales", headers=headers_a, json=body_a)
    assert sale_a.status_code == 200, sale_a.text
    sale_b = await ac.post("/api/v1/pos/sales", headers=headers_b, json=body_b)
    assert sale_b.status_code == 200, sale_b.text
    assert sale_a.json()["data"]["id"] != sale_b.json()["data"]["id"]

    replay_a = await ac.post("/api/v1/pos/sales", headers=headers_a, json=body_a)
    assert replay_a.status_code == 200, replay_a.text
    assert replay_a.json()["data"]["replayed"] is True
    assert replay_a.json()["data"]["id"] == sale_a.json()["data"]["id"]

    # --- Bank clearing group stamps company_id from statement ---
    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=seed["c1"].id
    )
    cash = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "1000", company_id=seed["c1"].id
    )
    e1 = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["super"].id,
        description="P21 Deposit",
        company_id=seed["c1"].id,
        lines=[
            {"account_code": "1000", "debit": 40, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 40},
        ],
    )
    e2 = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["super"].id,
        description="P21 Deposit 2",
        company_id=seed["c1"].id,
        lines=[
            {"account_code": "1000", "debit": 60, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 60},
        ],
    )
    jl1 = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == e1.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()
    jl2 = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == e2.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()
    day = datetime.utcnow()
    stmt = await recon.create_statement(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["super"].id,
        account_id=cash.id,
        statement_date=day,
        opening_balance=0,
        closing_balance=100,
        company_id=seed["c1"].id,
        lines=[
            {"txn_date": day, "amount": 40, "description": "P21 Part 1"},
            {"txn_date": day, "amount": 60, "description": "P21 Part 2"},
        ],
    )
    bank_lines = await recon.list_statement_lines(db_session, seed["t1"].id, stmt.id)
    result = await recon.create_clearing_group(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["super"].id,
        statement_id=stmt.id,
        statement_line_ids=[bank_lines[0].id, bank_lines[1].id],
        journal_line_ids=[jl1.id, jl2.id],
    )
    await db_session.commit()
    assert result["mode"] == "group"
    group = await db_session.get(m.BankClearingGroup, result["group"]["id"])
    assert group is not None
    assert group.company_id == seed["c1"].id
    links = (
        await db_session.execute(
            select(m.BankClearingBookLink).where(
                m.BankClearingBookLink.group_id == group.id
            )
        )
    ).scalars().all()
    assert links
    assert all(link.company_id == seed["c1"].id for link in links)


@pytest.mark.asyncio
async def test_expense_bank_idor_and_transfer_stamps_company_scoped(client, db_session):
    """Phase 22: expense/bank mutate IDOR + transfer movement company stamps."""
    from datetime import datetime

    from app import accounting as accounting_svc
    from app import bank_recon as recon

    ac, seed = client
    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=seed["c1"].id
    )

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="IDOR22",
        name="Alpha IDOR B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )
    exp_b = m.Expense(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        category="ops",
        description="Company B expense",
        amount=25,
        status="pending",
        created_by=seed["super"].id,
        approval_step=1,
        approval_steps_required=1,
    )
    db_session.add(exp_b)
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id
    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    # Company A cannot approve/reject/delete company B expense
    for method, path in (
        ("post", f"/api/v1/expenses/{exp_b.id}/approve"),
        ("post", f"/api/v1/expenses/{exp_b.id}/reject"),
        ("delete", f"/api/v1/expenses/{exp_b.id}"),
        ("get", f"/api/v1/expenses/{exp_b.id}/attachment"),
    ):
        if method == "post" and path.endswith("/reject"):
            r = await ac.post(path, headers=headers_a, json={"reason": "nope"})
        elif method == "post":
            r = await getattr(ac, method)(path, headers=headers_a, json={})
        else:
            r = await getattr(ac, method)(path, headers=headers_a)
        assert r.status_code == 404, (path, r.status_code, r.text)

    # Bank statement complete IDOR: create statement in B, mutate from A
    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=c_b.id
    )
    cash_b = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "1000", company_id=c_b.id
    )
    day = datetime.utcnow()
    stmt_b = await recon.create_statement(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["super"].id,
        account_id=cash_b.id,
        statement_date=day,
        opening_balance=0,
        closing_balance=0,
        company_id=c_b.id,
        lines=[],
    )
    await db_session.commit()
    complete = await ac.post(
        f"/api/v1/accounting/bank-statements/{stmt_b.id}/complete",
        headers=headers_a,
    )
    assert complete.status_code == 404, complete.text
    auto = await ac.post(
        f"/api/v1/accounting/bank-statements/{stmt_b.id}/auto-clear",
        headers=headers_a,
        json={},
    )
    assert auto.status_code == 404, auto.text

    # Transfer ship stamps StockMovement.company_id
    store_from = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="From Store P22",
        code="P22F",
        is_active=True,
    )
    store_to = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="To Store P22",
        code="P22T",
        is_active=True,
    )
    db_session.add_all([store_from, store_to])
    await db_session.flush()
    wh_from = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store_from.id,
        name="From WH",
        code="P22WF",
        is_active=True,
    )
    wh_to = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store_to.id,
        name="To WH",
        code="P22WT",
        is_active=True,
    )
    db_session.add_all([wh_from, wh_to])
    await db_session.flush()
    seed["p1"].stock_qty = 10
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            warehouse_id=wh_from.id,
            product_id=seed["p1"].id,
            quantity=10,
        )
    )
    transfer = m.StockTransfer(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        transfer_number="TR-P22-1",
        from_store_id=store_from.id,
        to_store_id=store_to.id,
        from_warehouse_id=wh_from.id,
        to_warehouse_id=wh_to.id,
        status="requested",
        created_by=seed["super"].id,
    )
    db_session.add(transfer)
    await db_session.flush()
    db_session.add(
        m.StockTransferItem(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            transfer_id=transfer.id,
            product_id=seed["p1"].id,
            quantity=2,
        )
    )
    await db_session.commit()

    ship = await ac.post(
        f"/api/v1/stores/transfers/{transfer.id}/ship",
        headers=headers_a,
    )
    assert ship.status_code == 200, ship.text
    move = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.reference_id == transfer.id,
                m.StockMovement.movement_type == "transfer_out",
            )
        )
    ).scalar_one()
    assert move.company_id == seed["c1"].id

    # Serialize company_id on expense create in company A
    created = await ac.post(
        "/api/v1/expenses",
        headers=headers_a,
        json={"category": "ops", "description": "P22 expense", "amount": 12},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"].get("company_id") == seed["c1"].id


@pytest.mark.asyncio
async def test_phase23_notification_serialize_and_mutate_idor(client, db_session):
    """Phase 23: notification stamps, serialize peers, PR/party/journal IDOR."""
    from datetime import datetime, timedelta

    from app import notifications as notif_svc

    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="P23B",
        name="Alpha Phase23 B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="P23 Customer B",
        status="active",
        credit_limit=100,
    )
    supp_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="supplier",
        name="P23 Supplier B",
        status="active",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P23 Product B",
        sku="P23-SKU-B",
        selling_price=5,
        cost_price=2,
        stock_qty=1,
        minimum_stock=10,
        reorder_level=10,
        is_active=True,
    )
    db_session.add_all([cust_b, supp_b, prod_b])
    await db_session.flush()
    pr_b = m.PurchaseRequest(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        request_number="PR-P23-B",
        supplier_id=supp_b.id,
        status="pending",
        estimated_total=10,
        approval_step=1,
        approval_steps_required=1,
        created_by=seed["super"].id,
    )
    db_session.add(pr_b)
    await db_session.flush()
    db_session.add(
        m.PurchaseRequestItem(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            purchase_request_id=pr_b.id,
            product_id=prod_b.id,
            quantity=1,
            unit_price=10,
        )
    )

    inv_b = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        invoice_number="SI-P23-B",
        customer_id=cust_b.id,
        status="posted",
        total_amount=50,
        paid_amount=0,
        due_date=datetime.utcnow() + timedelta(days=1),
        created_by=seed["super"].id,
    )
    db_session.add(inv_b)
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id
    headers_b = await _super_headers(ac, seed)
    headers_b["X-Workspace-Kind"] = "company"
    headers_b["X-Company-ID"] = c_b.id

    # --- Mutate IDOR from company A against company B records ---
    for method, path, json_body in (
        ("post", f"/api/v1/purchasing/requests/{pr_b.id}/approve", {}),
        ("post", f"/api/v1/purchasing/requests/{pr_b.id}/reject", {"reason": "nope"}),
        ("patch", f"/api/v1/customers/{cust_b.id}", {"name": "Hacked"}),
        ("delete", f"/api/v1/customers/{cust_b.id}", None),
        ("post", f"/api/v1/customers/{cust_b.id}/contacts", {"name": "x", "email": "x@ex.com"}),
        ("patch", f"/api/v1/customers/{cust_b.id}/credit-limit", {"credit_limit": 1}),
        ("patch", f"/api/v1/suppliers/{supp_b.id}", {"name": "Hacked"}),
        ("delete", f"/api/v1/suppliers/{supp_b.id}", None),
        ("post", f"/api/v1/inventory/adjust/{prod_b.id}", {"quantity": 1, "reason": "correction"}),
    ):
        if json_body is None:
            r = await getattr(ac, method)(path, headers=headers_a)
        else:
            r = await getattr(ac, method)(path, headers=headers_a, json=json_body)
        assert r.status_code == 404, (path, r.status_code, r.text)

    # --- Notification scan stamps company_id ---
    created_n = await notif_svc.scan_low_stock(db_session, seed["t1"].id)
    assert created_n >= 1
    note = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "low_stock",
                m.Notification.entity_id == prod_b.id,
            )
        )
    ).scalar_one()
    assert note.company_id == c_b.id

    due_n = await notif_svc.scan_payment_due(db_session, seed["t1"].id, within_days=3)
    assert due_n >= 1
    pay_note = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == seed["t1"].id,
                m.Notification.category == "payment_due",
                m.Notification.entity_id == inv_b.id,
            )
        )
    ).scalar_one()
    assert pay_note.company_id == c_b.id
    await db_session.commit()

    # Company A notification list must not include company B stamped notes
    listed = await ac.get("/api/v1/notifications", headers=headers_a)
    assert listed.status_code == 200, listed.text
    ids = {n["id"] for n in listed.json()["data"]}
    assert note.id not in ids
    assert pay_note.id not in ids

    # --- Serialize company_id peers in company A ---
    prod = await ac.post(
        "/api/v1/products",
        headers=headers_a,
        json={"name": "P23 Product A", "sku": "P23-SKU-A", "selling_price": 3, "cost_price": 1},
    )
    assert prod.status_code == 200, prod.text
    assert prod.json()["data"].get("company_id") == seed["c1"].id

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers_a,
        json={"name": "P23 Customer A", "party_type": "registered"},
    )
    assert cust.status_code == 200, cust.text
    assert cust.json()["data"].get("company_id") == seed["c1"].id

    supp = await ac.post(
        "/api/v1/suppliers",
        headers=headers_a,
        json={"name": "P23 Supplier A"},
    )
    assert supp.status_code == 200, supp.text
    assert supp.json()["data"].get("company_id") == seed["c1"].id

    pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers_a,
        json={
            "supplier_id": supp.json()["data"]["id"],
            "items": [
                {
                    "product_id": prod.json()["data"]["id"],
                    "quantity": 1,
                    "unit_price": 2,
                }
            ],
        },
    )
    assert pr.status_code == 200, pr.text
    assert pr.json()["data"].get("company_id") == seed["c1"].id


@pytest.mark.asyncio
async def test_phase24_payment_export_serialize_and_idor(client, db_session):
    """Phase 24: payment mutate IDOR, nested exports, budgets, serialize peers."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="P24B",
        name="Alpha Phase24 B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="P24 Customer B",
        status="active",
        credit_limit=500,
    )
    supp_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="supplier",
        name="P24 Supplier B",
        status="active",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P24 Product B",
        sku="P24-SKU-B",
        selling_price=8,
        cost_price=3,
        stock_qty=5,
        is_active=True,
    )
    store_b = m.Store(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P24SB",
        name="P24 Store B",
        is_active=True,
    )
    exp_cat_b = m.ExpenseCategory(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P24ONLY",
        name="P24 Only Budget Cat",
        budget_amount=9999,
        is_active=True,
    )
    db_session.add_all([cust_b, supp_b, prod_b, store_b, exp_cat_b])
    await db_session.flush()
    db_session.add(
        m.ProductVariant(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            product_id=prod_b.id,
            name="Size L",
            sku="P24-SKU-B-L",
            selling_price=8,
            cost_price=3,
            is_active=True,
        )
    )
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    # --- Payment mutate IDOR ---
    for path, body in (
        (
            "/api/v1/sales/payments",
            {"customer_id": cust_b.id, "amount": 1, "payment_method": "cash"},
        ),
        (
            f"/api/v1/customers/{cust_b.id}/payments",
            {"customer_id": cust_b.id, "amount": 1, "payment_method": "cash"},
        ),
        (
            f"/api/v1/suppliers/{supp_b.id}/payments",
            {
                "supplier_id": supp_b.id,
                "amount": 1,
                "payment_method": "bank_transfer",
            },
        ),
    ):
        r = await ac.post(path, headers=headers_a, json=body)
        assert r.status_code == 404, (path, r.status_code, r.text)

    # --- Nested product read/export IDOR ---
    for path in (
        f"/api/v1/products/{prod_b.id}/variants",
        f"/api/v1/products/{prod_b.id}/variants/export",
        f"/api/v1/products/{prod_b.id}/batches/export",
        f"/api/v1/products/{prod_b.id}/warehouse-stock/export",
        f"/api/v1/customers/{cust_b.id}/history",
        f"/api/v1/suppliers/{supp_b.id}/history",
        f"/api/v1/stores/{store_b.id}/inventory",
        f"/api/v1/stores/{store_b.id}/inventory/export",
        f"/api/v1/stores/{store_b.id}/sales",
        f"/api/v1/stores/{store_b.id}/sales/export",
    ):
        r = await ac.get(path, headers=headers_a)
        assert r.status_code == 404, (path, r.status_code, r.text)

    # --- Budgets scoped to company A (B-only category must not appear) ---
    budgets = await ac.get("/api/v1/expenses/budgets", headers=headers_a)
    assert budgets.status_code == 200, budgets.text
    codes = {c.get("code") for c in budgets.json()["data"].get("categories") or []}
    assert "P24ONLY" not in codes

    # --- Serialize peers: contact + payment in company A ---
    contact = await ac.post(
        f"/api/v1/customers/{seed['party1'].id}/contacts",
        headers=headers_a,
        json={"name": "P24 Contact", "email": "p24@example.com"},
    )
    assert contact.status_code == 200, contact.text
    assert contact.json()["data"].get("company_id") == seed["c1"].id

    seed["p1"].selling_price = 10
    seed["p1"].stock_qty = 20
    seed["p1"].tax_exempt = True
    await db_session.commit()
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers_a,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    total = float(inv.json()["data"]["total_amount"])
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers_a)
    assert posted.status_code == 200, posted.text
    pay = await ac.post(
        "/api/v1/sales/payments",
        headers=headers_a,
        json={
            "customer_id": seed["party1"].id,
            "amount": total,
            "sales_invoice_id": invoice_id,
            "payment_method": "cash",
        },
    )
    assert pay.status_code == 200, pay.text
    pay_row = (
        await db_session.execute(
            select(m.CustomerPayment).where(m.CustomerPayment.id == pay.json()["data"]["id"])
        )
    ).scalar_one()
    assert pay_row.company_id == seed["c1"].id


@pytest.mark.asyncio
async def test_phase25_create_fk_serialize_and_reports(client, db_session):
    """Phase 25: create-path FK company asserts + transfer report scope."""
    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="P25B",
        name="Alpha Phase25 B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="P25 Customer B",
        status="active",
        credit_limit=100,
    )
    supp_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="supplier",
        name="P25 Supplier B",
        status="active",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P25 Product B",
        sku="P25-SKU-B",
        selling_price=5,
        cost_price=2,
        stock_qty=3,
        reorder_level=10,
        is_active=True,
    )
    store_b = m.Store(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P25SB",
        name="P25 Store B",
        is_active=True,
    )
    store_b2 = m.Store(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P25SB2",
        name="P25 Store B2",
        is_active=True,
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P25WB",
        name="P25 WH B",
        is_active=True,
    )
    exp_cat_b = m.ExpenseCategory(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P25CAT",
        name="P25 Expense Cat",
        budget_amount=100,
        is_active=True,
    )
    db_session.add_all([cust_b, supp_b, prod_b, store_b, store_b2, wh_b, exp_cat_b])
    await db_session.flush()
    wh_b.store_id = store_b.id
    xfer_b = m.StockTransfer(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        transfer_number="TR-P25-B",
        from_store_id=store_b.id,
        to_store_id=store_b2.id,
        from_warehouse_id=wh_b.id,
        to_warehouse_id=wh_b.id,
        status="draft",
        created_by=seed["super"].id,
    )
    db_session.add(xfer_b)
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    # --- Create FK IDOR ---
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers_a,
        json={
            "customer_id": cust_b.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert inv.status_code == 404, inv.text

    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers_a,
        json={
            "customer_id": cust_b.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert quote.status_code == 404, quote.text

    pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers_a,
        json={
            "supplier_id": supp_b.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert pr.status_code == 404, pr.text

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers_a,
        json={
            "supplier_id": supp_b.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert po.status_code == 404, po.text

    # Product from B on otherwise valid A customer
    inv_prod = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers_a,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": prod_b.id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert inv_prod.status_code == 404, inv_prod.text

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers_a,
        json={"product_id": prod_b.id, "quantity": 1},
    )
    assert stock_in.status_code == 404, stock_in.text

    stock_out = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers_a,
        json={"product_id": prod_b.id, "quantity": 1},
    )
    assert stock_out.status_code == 404, stock_out.text

    reorder = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers_a,
        json={"product_id": prod_b.id, "supplier_id": supp_b.id},
    )
    assert reorder.status_code == 404, reorder.text

    xfer = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers_a,
        json={
            "from_store_id": store_b.id,
            "to_store_id": store_b2.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert xfer.status_code == 404, xfer.text

    count = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers_a,
        json={"warehouse_id": wh_b.id},
    )
    assert count.status_code == 404, count.text

    exp = await ac.post(
        "/api/v1/expenses",
        headers=headers_a,
        json={
            "category_id": exp_cat_b.id,
            "description": "cross company",
            "amount": 5,
        },
    )
    assert exp.status_code == 404, exp.text

    # --- Transfer report must not list company B transfer ---
    report = await ac.get("/api/v1/reports/transfers", headers=headers_a)
    assert report.status_code == 200, report.text
    ids = {t["id"] for t in report.json()["data"].get("transfers") or []}
    assert xfer_b.id not in ids

    # --- Serialize child company_id on stock count item (company A) ---
    # Ensure company A has a warehouse
    wh_a = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.company_id == seed["c1"].id,
            )
        )
    ).scalars().first()
    if wh_a is None:
        store_a = m.Store(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            code="P25SA",
            name="P25 Store A",
            is_active=True,
        )
        db_session.add(store_a)
        await db_session.flush()
        wh_a = m.Warehouse(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            store_id=store_a.id,
            code="P25WA",
            name="P25 WH A",
            is_active=True,
        )
        db_session.add(wh_a)
        await db_session.commit()

    sc = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers_a,
        json={"warehouse_id": wh_a.id, "product_ids": [seed["p1"].id]},
    )
    assert sc.status_code == 200, sc.text
    items = sc.json()["data"].get("items") or []
    assert items
    assert all(i.get("company_id") == seed["c1"].id for i in items)


@pytest.mark.asyncio
async def test_phase26_create_fk_serialize_and_scope(client, db_session):
    """Phase 26: deeper create FK, document-line serialize, warehouse-stock scope."""
    from datetime import datetime

    from app import accounting as accounting_svc

    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="P26B",
        name="Alpha Phase26 B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="P26 Customer B",
        status="active",
        credit_limit=100,
    )
    supp_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="supplier",
        name="P26 Supplier B",
        status="active",
        credit_limit=0,
    )
    supp_a = m.Party(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        kind="supplier",
        name="P26 Supplier A",
        status="active",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P26 Product B",
        sku="P26-SKU-B",
        selling_price=9,
        cost_price=3,
        stock_qty=8,
        is_active=True,
    )
    db_session.add_all([cust_b, supp_b, supp_a, prod_b])
    await db_session.flush()

    po_b = m.PurchaseOrder(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        po_number="PO-P26-B",
        supplier_id=supp_b.id,
        status="sent",
        subtotal=9,
        tax_amount=0,
        total_amount=9,
        created_by=seed["super"].id,
    )
    db_session.add(po_b)
    await db_session.flush()
    po_item_b = m.PurchaseOrderItem(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        purchase_order_id=po_b.id,
        product_id=prod_b.id,
        quantity=1,
        unit_price=9,
        line_total=9,
    )
    db_session.add(po_item_b)
    await db_session.flush()

    grn_b = m.GoodsReceipt(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        grn_number="GRN-P26-B",
        purchase_order_id=po_b.id,
        supplier_id=supp_b.id,
        status="posted",
        created_by=seed["super"].id,
    )
    db_session.add(grn_b)
    await db_session.flush()
    grn_item_b = m.GoodsReceiptItem(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        goods_receipt_id=grn_b.id,
        po_item_id=po_item_b.id,
        product_id=prod_b.id,
        received_qty=1,
        accepted_qty=1,
    )
    db_session.add(grn_item_b)

    inv_b = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        invoice_number="INV-P26-B",
        customer_id=cust_b.id,
        status="posted",
        subtotal=9,
        tax_amount=0,
        total_amount=9,
        posted_at=datetime.utcnow(),
        created_by=seed["super"].id,
    )
    db_session.add(inv_b)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            sales_invoice_id=inv_b.id,
            product_id=prod_b.id,
            quantity=1,
            unit_price=9,
            line_total=9,
        )
    )

    rec_b = m.RecurringExpense(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        category="ops",
        description="P26 recurring B",
        amount=15,
        frequency="monthly",
        created_by=seed["super"].id,
    )
    db_session.add(rec_b)

    # Company A rows for serialize + warehouse-stock
    po_a = m.PurchaseOrder(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        po_number="PO-P26-A",
        supplier_id=supp_a.id,
        status="draft",
        subtotal=5,
        tax_amount=0,
        total_amount=5,
        created_by=seed["super"].id,
    )
    db_session.add(po_a)
    await db_session.flush()
    po_item_a = m.PurchaseOrderItem(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        purchase_order_id=po_a.id,
        product_id=seed["p1"].id,
        quantity=1,
        unit_price=5,
        line_total=5,
    )
    db_session.add(po_item_a)

    inv_a = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        invoice_number="INV-P26-A",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=5,
        tax_amount=0,
        total_amount=5,
        posted_at=datetime.utcnow(),
        created_by=seed["super"].id,
    )
    db_session.add(inv_a)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            sales_invoice_id=inv_a.id,
            product_id=seed["p1"].id,
            quantity=1,
            unit_price=5,
            line_total=5,
        )
    )

    store_a = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        code="P26SA",
        name="P26 Store A",
        is_active=True,
    )
    store_a2 = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        code="P26SA2",
        name="P26 Store A2",
        is_active=True,
    )
    db_session.add_all([store_a, store_a2])
    await db_session.flush()
    wh_a = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store_a.id,
        code="P26WA",
        name="P26 WH A",
        is_active=True,
    )
    wh_a2 = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store_a2.id,
        code="P26WA2",
        name="P26 WH A2",
        is_active=True,
    )
    db_session.add_all([wh_a, wh_a2])
    await db_session.flush()

    grn_a = m.GoodsReceipt(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        grn_number="GRN-P26-A",
        purchase_order_id=po_a.id,
        supplier_id=supp_a.id,
        warehouse_id=wh_a.id,
        status="posted",
        created_by=seed["super"].id,
    )
    db_session.add(grn_a)
    await db_session.flush()
    db_session.add(
        m.GoodsReceiptItem(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            goods_receipt_id=grn_a.id,
            po_item_id=po_item_a.id,
            product_id=seed["p1"].id,
            received_qty=1,
            accepted_qty=1,
        )
    )

    xfer_a = m.StockTransfer(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        transfer_number="TR-P26-A",
        from_store_id=store_a.id,
        to_store_id=store_a2.id,
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_a2.id,
        status="draft",
        created_by=seed["super"].id,
    )
    db_session.add(xfer_a)
    await db_session.flush()
    db_session.add(
        m.StockTransferItem(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            transfer_id=xfer_a.id,
            product_id=seed["p1"].id,
            quantity=1,
        )
    )

    db_session.add(
        m.WarehouseStock(
            tenant_id=seed["t1"].id,
            company_id=seed["c1"].id,
            warehouse_id=wh_a.id,
            product_id=seed["p1"].id,
            quantity=4,
        )
    )
    # Sibling-company stock row on same product must not appear under company A
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P26WB",
        name="P26 WH B",
        is_active=True,
    )
    db_session.add(wh_b)
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            warehouse_id=wh_b.id,
            product_id=seed["p1"].id,
            quantity=99,
        )
    )

    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=seed["c1"].id
    )
    cash = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "1000", company_id=seed["c1"].id
    )
    rev = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "4000", company_id=seed["c1"].id
    )
    je = m.JournalEntry(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        entry_number="JE-P26-A",
        description="P26 journal",
        total_debit=10,
        total_credit=10,
        status="posted",
        created_by=seed["super"].id,
    )
    db_session.add(je)
    await db_session.flush()
    db_session.add_all(
        [
            m.JournalEntryLine(
                tenant_id=seed["t1"].id,
                company_id=seed["c1"].id,
                journal_entry_id=je.id,
                account_id=cash.id,
                debit=10,
                credit=0,
            ),
            m.JournalEntryLine(
                tenant_id=seed["t1"].id,
                company_id=seed["c1"].id,
                journal_entry_id=je.id,
                account_id=rev.id,
                debit=0,
                credit=10,
            ),
        ]
    )
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    # --- Create FK IDOR ---
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers_a,
        json={
            "purchase_order_id": po_b.id,
            "items": [{"po_item_id": po_item_b.id, "received_qty": 1}],
        },
    )
    assert grn.status_code == 404, grn.text

    pret = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers_a,
        json={
            "goods_receipt_id": grn_b.id,
            "items": [{"goods_receipt_item_id": grn_item_b.id, "quantity": 1}],
        },
    )
    assert pret.status_code == 404, pret.text

    pi = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers_a,
        json={"goods_receipt_id": grn_b.id},
    )
    assert pi.status_code == 404, pi.text

    sret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers_a,
        json={
            "sales_invoice_id": inv_b.id,
            "items": [{"product_id": prod_b.id, "quantity": 1}],
        },
    )
    assert sret.status_code == 404, sret.text

    patch_rec = await ac.patch(
        f"/api/v1/expenses/recurring/{rec_b.id}",
        headers=headers_a,
        json={"amount": 1},
    )
    assert patch_rec.status_code == 404, patch_rec.text

    # PO amend with sibling-company product
    amend = await ac.patch(
        f"/api/v1/purchasing/orders/{po_a.id}",
        headers=headers_a,
        json={
            "items": [
                {
                    "product_id": prod_b.id,
                    "quantity": 1,
                    "unit_price": 5,
                }
            ],
        },
    )
    assert amend.status_code == 404, amend.text

    # POS sale with sibling-company product
    seed["p1"].selling_price = 10
    seed["p1"].stock_qty = 20
    seed["p1"].reserved_qty = 0
    seed["p1"].tax_exempt = True
    seed["p1"].tax_rate_id = None
    prod_b.selling_price = 9
    prod_b.stock_qty = 8
    await db_session.commit()
    open_a = await ac.post(
        "/api/v1/pos/sessions/open", headers=headers_a, json={"opening_cash": 0}
    )
    assert open_a.status_code == 200, open_a.text
    pos = await ac.post(
        "/api/v1/pos/sales",
        headers=headers_a,
        json={
            "session_id": open_a.json()["data"]["session_id"],
            "items": [{"product_id": prod_b.id, "quantity": 1}],
            "payments": [{"payment_method": "cash", "amount": 9}],
        },
    )
    assert pos.status_code == 404, pos.text

    # --- Serialize nested company_id ---
    get_inv = await ac.get(f"/api/v1/sales/invoices/{inv_a.id}", headers=headers_a)
    assert get_inv.status_code == 200, get_inv.text
    inv_items = get_inv.json()["data"].get("items") or []
    assert inv_items
    assert all(i.get("company_id") == seed["c1"].id for i in inv_items)

    get_po = await ac.get(f"/api/v1/purchasing/orders/{po_a.id}", headers=headers_a)
    assert get_po.status_code == 200, get_po.text
    po_items = get_po.json()["data"].get("items") or []
    assert po_items
    assert all(i.get("company_id") == seed["c1"].id for i in po_items)

    get_grn = await ac.get(f"/api/v1/purchasing/grn/{grn_a.id}", headers=headers_a)
    assert get_grn.status_code == 200, get_grn.text
    grn_items = get_grn.json()["data"].get("items") or []
    assert grn_items
    assert all(i.get("company_id") == seed["c1"].id for i in grn_items)

    get_xfer = await ac.get(f"/api/v1/stores/transfers/{xfer_a.id}", headers=headers_a)
    assert get_xfer.status_code == 200, get_xfer.text
    xfer_items = get_xfer.json()["data"].get("items") or []
    assert xfer_items
    assert all(i.get("company_id") == seed["c1"].id for i in xfer_items)

    get_je = await ac.get(
        f"/api/v1/accounting/journal-entries/{je.id}", headers=headers_a
    )
    assert get_je.status_code == 200, get_je.text
    je_lines = get_je.json()["data"].get("lines") or []
    assert je_lines
    assert all(ln.get("company_id") == seed["c1"].id for ln in je_lines)

    # --- Warehouse-stock scope ---
    stock = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/warehouse-stock", headers=headers_a
    )
    assert stock.status_code == 200, stock.text
    wh_rows = stock.json()["data"].get("warehouses") or []
    assert wh_rows
    assert all(r.get("company_id") == seed["c1"].id for r in wh_rows)
    assert all(r.get("warehouse_id") != wh_b.id for r in wh_rows)


@pytest.mark.asyncio
async def test_phase27_create_fk_and_scan_scope(client, db_session):
    """Phase 27: settlement/group/dept/tax/hold/warehouse FK + quotation scan scope."""
    from datetime import datetime, timedelta

    from app import accounting as accounting_svc

    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="P27B",
        name="Alpha Phase27 B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="P27 Customer B",
        status="active",
        credit_limit=50,
    )
    supp_a = m.Party(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        kind="supplier",
        name="P27 Supplier A",
        status="active",
        credit_limit=0,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P27 Product B",
        sku="P27-SKU-B",
        selling_price=7,
        cost_price=2,
        stock_qty=20,
        reserved_qty=0,
        is_active=True,
    )
    group_b = m.CustomerGroup(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P27 Group B",
        discount_percent=5,
        is_active=True,
    )
    dept_b = m.Department(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P27D",
        name="P27 Dept B",
        is_active=True,
    )
    tax_b = m.TaxRate(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P27 Tax B",
        rate=12.5,
        tax_type="vat",
        is_active=True,
    )
    store_b = m.Store(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P27SB",
        name="P27 Store B",
        is_active=True,
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P27WB",
        name="P27 WH B",
        is_active=True,
    )
    db_session.add_all(
        [cust_b, supp_a, prod_b, group_b, dept_b, tax_b, store_b, wh_b]
    )
    await db_session.flush()
    wh_b.store_id = store_b.id

    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=c_b.id
    )
    cash_b = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "1000", company_id=c_b.id
    )
    assert cash_b is not None

    quote_b = m.SalesQuotation(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        quotation_number="QT-P27-B",
        customer_id=cust_b.id,
        status="sent",
        subtotal=7,
        tax_amount=0,
        total_amount=7,
        valid_until=datetime.utcnow() - timedelta(days=1),
        created_by=seed["super"].id,
    )
    quote_a = m.SalesQuotation(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        quotation_number="QT-P27-A",
        customer_id=seed["party1"].id,
        status="sent",
        subtotal=5,
        tax_amount=0,
        total_amount=5,
        valid_until=datetime.utcnow() - timedelta(days=1),
        created_by=seed["super"].id,
    )
    db_session.add_all([quote_b, quote_a])
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    # Settlement liquid account from B
    exp = await ac.post(
        "/api/v1/expenses",
        headers=headers_a,
        json={
            "category": "ops",
            "description": "cross liquid",
            "amount": 3,
            "liquid_account_id": cash_b.id,
        },
    )
    assert exp.status_code == 404, exp.text

    # Journal store from B
    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=seed["c1"].id
    )
    je = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers_a,
        json={
            "description": "P27 cross store",
            "store_id": store_b.id,
            "lines": [
                {"account_code": "1000", "debit": 1, "credit": 0},
                {"account_code": "4000", "debit": 0, "credit": 1},
            ],
        },
    )
    assert je.status_code == 404, je.text

    # Customer group from B
    cust = await ac.post(
        "/api/v1/customers",
        headers=headers_a,
        json={"name": "P27 Cust A", "customer_group_id": group_b.id},
    )
    assert cust.status_code == 404, cust.text

    # Department from B
    exp_dept = await ac.post(
        "/api/v1/expenses",
        headers=headers_a,
        json={
            "category": "ops",
            "description": "cross dept",
            "amount": 2,
            "department_id": dept_b.id,
        },
    )
    assert exp_dept.status_code == 404, exp_dept.text

    # Product tax_rate from B
    prod = await ac.post(
        "/api/v1/products",
        headers=headers_a,
        json={
            "name": "P27 Taxed",
            "sku": "P27-TAX-A",
            "selling_price": 1,
            "cost_price": 0.5,
            "tax_rate_id": tax_b.id,
        },
    )
    assert prod.status_code == 404, prod.text

    # POS hold soft-reserve sibling product
    reserved_before = float(prod_b.reserved_qty or 0)
    hold = await ac.post(
        "/api/v1/pos/holds",
        headers=headers_a,
        json={
            "label": "P27 cross",
            "reserve_stock": True,
            "cart_payload": {"items": [{"product_id": prod_b.id, "quantity": 1}]},
        },
    )
    assert hold.status_code == 404, hold.text
    await db_session.refresh(prod_b)
    assert float(prod_b.reserved_qty or 0) == reserved_before

    # PO warehouse from B
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers_a,
        json={
            "supplier_id": supp_a.id,
            "warehouse_id": wh_b.id,
            "items": [
                {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}
            ],
        },
    )
    assert po.status_code == 404, po.text

    # Quotation scan must not expire company B quote when run from A
    scan = await ac.post("/api/v1/notifications/scan-due", headers=headers_a)
    assert scan.status_code == 200, scan.text
    await db_session.refresh(quote_b)
    await db_session.refresh(quote_a)
    assert quote_b.status == "sent"
    assert quote_a.status == "expired"


@pytest.mark.asyncio
async def test_phase28_scan_warehouse_coa_uom_scope(client, db_session):
    """Phase 28: scan scope, warehouse/COA/UoM FK, expense category GL."""
    from datetime import datetime, timedelta

    from app import accounting as accounting_svc

    ac, seed = client

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="P28B",
        name="Alpha Phase28 B",
        industry="retail",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            user_id=seed["super"].id,
            company_id=c_b.id,
            role="super_admin",
            is_active=True,
        )
    )

    cust_b = m.Party(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        kind="customer",
        name="P28 Customer B",
        status="active",
        credit_limit=50,
    )
    prod_b = m.Product(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        name="P28 Product B",
        sku="P28-SKU-B",
        selling_price=4,
        cost_price=1,
        stock_qty=10,
        is_active=True,
    )
    store_b = m.Store(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P28SB",
        name="P28 Store B",
        is_active=True,
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P28WB",
        name="P28 WH B",
        is_active=True,
    )
    unit_b = m.UnitOfMeasure(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P28BX",
        name="P28 Box",
        conversion_factor=1,
        is_active=True,
    )
    cat_b = m.ExpenseCategory(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        code="P28CAT",
        name="P28 Only Cat",
        budget_amount=100,
        is_active=True,
    )
    db_session.add_all([cust_b, prod_b, store_b, wh_b, unit_b, cat_b])
    await db_session.flush()
    wh_b.store_id = store_b.id

    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=c_b.id
    )
    await accounting_svc.ensure_default_accounts(
        db_session, seed["t1"].id, company_id=seed["c1"].id
    )
    exp_acct_b = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "6000", company_id=c_b.id
    )
    parent_b = await accounting_svc.get_account_by_code(
        db_session, seed["t1"].id, "1000", company_id=c_b.id
    )

    inv_b = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        invoice_number="INV-P28-B",
        customer_id=cust_b.id,
        status="posted",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        paid_amount=0,
        due_date=datetime.utcnow() - timedelta(days=1),
        posted_at=datetime.utcnow(),
        created_by=seed["super"].id,
    )
    inv_a = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        invoice_number="INV-P28-A",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=20,
        tax_amount=0,
        total_amount=20,
        paid_amount=0,
        due_date=datetime.utcnow() - timedelta(days=1),
        posted_at=datetime.utcnow(),
        created_by=seed["super"].id,
    )
    rec_b = m.RecurringExpense(
        tenant_id=seed["t1"].id,
        company_id=c_b.id,
        category="ops",
        description="P28 recurring B",
        amount=9,
        frequency="monthly",
        next_run_at=datetime.utcnow() - timedelta(hours=1),
        created_by=seed["super"].id,
    )
    db_session.add_all([inv_b, inv_a, rec_b])
    await db_session.commit()

    headers_a = await _super_headers(ac, seed)
    headers_a["X-Workspace-Kind"] = "company"
    headers_a["X-Company-ID"] = seed["c1"].id

    # Stock mutate with sibling warehouse
    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers_a,
        json={
            "product_id": seed["p1"].id,
            "quantity": 1,
            "warehouse_id": wh_b.id,
        },
    )
    assert stock_in.status_code == 404, stock_in.text

    adjust = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=headers_a,
        json={"quantity": 1, "reason": "damage", "warehouse_id": wh_b.id},
    )
    assert adjust.status_code == 404, adjust.text

    # Expense category with sibling GL account
    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers_a,
        json={
            "code": "P28A",
            "name": "P28 A Cat",
            "account_id": exp_acct_b.id,
            "budget_amount": 10,
        },
    )
    assert cat.status_code == 404, cat.text

    # COA parent from sibling company
    coa = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers_a,
        json={
            "code": "P2810",
            "name": "P28 Nested Cash",
            "account_type": "asset",
            "parent_id": parent_b.id,
        },
    )
    assert coa.status_code == 404, coa.text

    # UoM convert / create with sibling base
    conv = await ac.get(
        "/api/v1/catalog/units/convert",
        headers=headers_a,
        params={
            "from_unit_id": unit_b.id,
            "to_unit_id": unit_b.id,
            "quantity": 1,
        },
    )
    assert conv.status_code == 404, conv.text

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers_a,
        json={
            "code": "P28PK",
            "name": "P28 Pack",
            "base_unit_id": unit_b.id,
            "conversion_factor": 6,
        },
    )
    assert unit.status_code == 404, unit.text

    # Scan-due must not notify/mutate company B
    last_b_before = rec_b.last_notified_for
    scan = await ac.post("/api/v1/notifications/scan-due", headers=headers_a)
    assert scan.status_code == 200, scan.text
    await db_session.refresh(rec_b)
    assert rec_b.last_notified_for == last_b_before
    notes = await ac.get("/api/v1/notifications", headers=headers_a)
    assert notes.status_code == 200, notes.text
    entity_ids = {n.get("entity_id") for n in notes.json()["data"]}
    assert inv_b.id not in entity_ids
    assert rec_b.id not in entity_ids
    assert inv_a.id in entity_ids or any(
        "INV-P28-A" in (n.get("message") or "") for n in notes.json()["data"]
    )
