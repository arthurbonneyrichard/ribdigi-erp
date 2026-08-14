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
