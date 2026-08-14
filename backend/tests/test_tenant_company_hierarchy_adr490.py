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
