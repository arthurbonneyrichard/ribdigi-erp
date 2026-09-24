"""Cross-tenant isolation matrix for core ERP resources."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.accounting import ensure_default_accounts, post_journal_entry
from app.backup import create_backup
from app.expenses import create_expense, ensure_default_categories
from app.notifications import create_notification
from app.purchasing import create_purchase_invoice
from app.stores import create_store
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr_headers(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_customers_list_excludes_other_tenant(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    r = await ac.get("/api/v1/customers", headers=headers)
    assert r.status_code == 200, r.text
    names = {row["name"] for row in r.json()["data"]}
    assert "Alpha Customer" in names
    assert "Beta Customer" not in names


@pytest.mark.asyncio
async def test_suppliers_list_excludes_other_tenant(client):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    r = await ac.get("/api/v1/suppliers", headers=headers)
    assert r.status_code == 200, r.text
    names = {row["name"] for row in r.json()["data"]}
    assert "Beta Supplier" not in names


@pytest.mark.asyncio
async def test_foreign_customer_credit_statement_404(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    r = await ac.get(
        f"/api/v1/credit/customers/{seed['party2'].id}/statement",
        headers=headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_customer_credit_limit_patch_404(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    r = await ac.patch(
        f"/api/v1/customers/{seed['party2'].id}/credit-limit",
        headers=headers,
        json={"credit_limit": 50},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_product_image_404(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    r = await ac.get(f"/api/v1/products/{seed['p2'].id}/image", headers=headers)
    assert r.status_code in {404, 400}


@pytest.mark.asyncio
async def test_expense_get_and_list_isolation(client, db_session):
    ac, seed = client
    await ensure_default_categories(db_session, seed["t2"].id)
    await db_session.commit()
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t2"].id)
        )
    ).scalars().all()
    expense = await create_expense(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        amount=25,
        description="Beta secret expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    await db_session.commit()

    headers = await _mgr_headers(ac)
    missing = await ac.get(f"/api/v1/expenses/{expense.id}", headers=headers)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/expenses", headers=headers)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["data"]}
    assert expense.id not in ids


@pytest.mark.asyncio
async def test_purchase_invoice_isolation(client, db_session):
    ac, seed = client
    inv = await create_purchase_invoice(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        supplier_id=seed["supplier2"].id,
        items=[
            {
                "product_id": seed["p2"].id,
                "quantity": 1,
                "unit_price": 3,
            }
        ],
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.get(f"/api/v1/purchasing/invoices/{inv.id}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_tax_rate_isolation(client, db_session):
    ac, seed = client
    rate = m.TaxRate(
        tenant_id=seed["t2"].id,
        name="Beta VAT Secret",
        rate=12.5,
        is_default=True,
        is_active=True,
    )
    db_session.add(rate)
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    missing = await ac.get(f"/api/v1/tax/rates/{rate.id}", headers=headers)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/tax/rates", headers=headers)
    assert listed.status_code == 200
    names = {row.get("name") for row in listed.json()["data"]}
    assert "Beta VAT Secret" not in names


@pytest.mark.asyncio
async def test_store_inventory_isolation(client, db_session):
    ac, seed = client
    store = await create_store(
        db_session,
        tenant_id=seed["t2"].id,
        name="Beta Store",
        code="BST",
    )
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.get(f"/api/v1/stores/{store.id}/inventory", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pos_session_isolation(client):
    ac, seed = client
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=beta,
        json={"opening_cash": 10},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    alpha = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    drawer = await ac.get(f"/api/v1/pos/sessions/{session_id}/drawer", headers=alpha)
    assert drawer.status_code == 404

    listed = await ac.get("/api/v1/pos/sessions", headers=alpha)
    assert listed.status_code == 200
    ids = {row.get("session_id") or row.get("id") for row in listed.json()["data"]}
    assert session_id not in ids


@pytest.mark.asyncio
async def test_notification_isolation(client, db_session):
    ac, seed = client
    note = await create_notification(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        category="system",
        title="Beta secret alert",
        message="Should not leak",
    )
    assert note is not None
    await db_session.commit()

    headers = await _mgr_headers(ac)
    mark = await ac.patch(f"/api/v1/notifications/{note.id}/read", headers=headers)
    assert mark.status_code == 404

    listed = await ac.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200
    titles = {row.get("title") for row in listed.json()["data"]}
    assert "Beta secret alert" not in titles


@pytest.mark.asyncio
async def test_backup_isolation(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    job = await create_backup(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    missing = await ac.get(f"/api/v1/backup/{job.id}", headers=headers)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/backup", headers=headers)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["data"]}
    assert job.id not in ids


@pytest.mark.asyncio
async def test_accounting_accounts_and_journals_isolation(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t1"].id)
    await ensure_default_accounts(db_session, seed["t2"].id)
    await post_journal_entry(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        description="Beta secret journal",
        reference="BETA-J-1",
        lines=[
            {"account_code": "1000", "debit": 10, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 10},
        ],
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 200
    alpha_ids = {row["id"] for row in accounts.json()["data"]}
    beta_accounts = (
        await db_session.execute(
            select(m.Account.id).where(m.Account.tenant_id == seed["t2"].id)
        )
    ).scalars().all()
    assert alpha_ids.isdisjoint(set(beta_accounts))

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert journals.status_code == 200
    refs = {
        (row.get("reference") or "") + (row.get("description") or "")
        for row in journals.json()["data"]
    }
    assert not any("Beta secret journal" in x for x in refs)
    assert not any("BETA-J-1" in x for x in refs)


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_credit_aging(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    headers["X-Tenant-ID"] = seed["t2"].id
    r = await ac.get("/api/v1/credit/aging", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_isolation(client, db_session):
    ac, seed = client
    from app import audit as audit_svc

    await audit_svc.record_event(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        module="system",
        action="beta_secret_audit",
        entity="tenant",
        entity_id=seed["t2"].id,
        details={"secret": "beta-only"},
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    listed = await ac.get("/api/v1/audit-logs", headers=headers)
    assert listed.status_code == 200
    actions = {row.get("action") for row in listed.json()["data"]}
    assert "beta_secret_audit" not in actions


@pytest.mark.asyncio
async def test_bank_connection_isolation(client, db_session):
    ac, seed = client
    from app import bank_connectors as bank_connectors_svc

    await ensure_default_accounts(db_session, seed["t2"].id)
    bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    conn = await bank_connectors_svc.create_connection(
        db_session,
        tenant_id=seed["t2"].id,
        account_id=bank.id,
        provider="mock",
        display_name="Beta Bank Secret",
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    missing = await ac.patch(
        f"/api/v1/accounting/bank-connections/{conn.id}",
        headers=headers,
        json={"display_name": "Hijack"},
    )
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/accounting/bank-connections", headers=headers)
    assert listed.status_code == 200
    names = {row.get("display_name") for row in listed.json()["data"]}
    assert "Beta Bank Secret" not in names


@pytest.mark.asyncio
async def test_report_schedule_isolation(client, db_session):
    ac, seed = client
    from app import report_schedules as report_schedules_svc

    schedule = await report_schedules_svc.create_schedule(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        name="Beta Secret Schedule",
        report_type="sales_daily",
        format="csv",
        frequency="daily",
        hour_utc=6,
        recipients=["beta@example.com"],
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    missing = await ac.delete(
        f"/api/v1/reports/schedules/{schedule.id}",
        headers=headers,
    )
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/reports/schedules", headers=headers)
    assert listed.status_code == 200
    names = {row.get("name") for row in listed.json()["data"]}
    assert "Beta Secret Schedule" not in names


@pytest.mark.asyncio
async def test_ai_insights_are_tenant_scoped(client, db_session):
    ac, seed = client
    # Ensure beta has distinct low-stock signal while alpha insights stay scoped.
    seed["p2"].stock_qty = 0
    seed["p2"].reorder_level = 5
    await db_session.commit()

    alpha = await _mgr_headers(ac)
    r = await ac.get("/api/v1/ai/insights", headers=alpha)
    assert r.status_code == 200, r.text
    text = " ".join(r.json()["data"].get("insights") or [])
    assert "Beta" not in text

    chat = await ac.post("/api/v1/ai/chat", headers=alpha, json={"message": "hi"})
    assert chat.status_code == 503


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_users(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    headers["X-Tenant-ID"] = seed["t2"].id
    r = await ac.get("/api/v1/users", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cheque_isolation(client, db_session):
    ac, seed = client
    cheque = m.Cheque(
        tenant_id=seed["t2"].id,
        direction="received",
        status="pending",
        cheque_number="BETA-CHQ-1",
        amount=55,
        party_id=seed["party2"].id,
        created_by=seed["u2"].id,
    )
    db_session.add(cheque)
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    missing = await ac.get(f"/api/v1/accounting/cheques/{cheque.id}", headers=headers)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert listed.status_code == 200
    numbers = {row.get("cheque_number") for row in listed.json()["data"]}
    assert "BETA-CHQ-1" not in numbers


@pytest.mark.asyncio
async def test_stock_transfer_isolation(client, db_session):
    ac, seed = client
    from_store = await create_store(
        db_session, tenant_id=seed["t2"].id, name="Beta From", code="BF1"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t2"].id, name="Beta To", code="BT1"
    )
    await db_session.flush()
    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t2"].id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    to_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t2"].id,
                m.Warehouse.store_id == to_store.id,
            )
        )
    ).scalar_one()
    transfer = m.StockTransfer(
        tenant_id=seed["t2"].id,
        transfer_number="TR-BETA-1",
        from_store_id=from_store.id,
        to_store_id=to_store.id,
        from_warehouse_id=from_wh.id,
        to_warehouse_id=to_wh.id,
        status="draft",
        created_by=seed["u2"].id,
    )
    db_session.add(transfer)
    await db_session.commit()

    headers = await _mgr_headers(ac)
    missing = await ac.get(f"/api/v1/stores/transfers/{transfer.id}", headers=headers)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/stores/transfers", headers=headers)
    assert listed.status_code == 200
    numbers = {row.get("transfer_number") for row in listed.json()["data"]}
    assert "TR-BETA-1" not in numbers


@pytest.mark.asyncio
async def test_media_key_tenant_mismatch_rejected():
    from fastapi import HTTPException

    from app.storage import validate_key

    with pytest.raises(HTTPException) as exc:
        validate_key(f"other-tenant/expenses/file.pdf", tenant_id="alpha-tenant")
    assert exc.value.status_code == 403
