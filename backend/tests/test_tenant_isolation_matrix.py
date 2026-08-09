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
    assert chat.status_code == 200, chat.text
    chat_body = chat.json()["data"]
    assert chat_body.get("method") == "rules_v1"
    assert "Beta" not in (chat_body.get("answer") or "")
    assert "Beta" not in (chat_body.get("reply") or "")


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


@pytest.mark.asyncio
async def test_foreign_expense_attachment_404(client, db_session):
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
        amount=12,
        description="Beta attached expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    expense.attachment_url = f"{seed['t2'].id}/expenses/beta-receipt.pdf"
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.get(f"/api/v1/expenses/{expense.id}/attachment", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_purchase_invoice_attachment_404(client, db_session):
    ac, seed = client
    inv = await create_purchase_invoice(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        supplier_id=seed["supplier2"].id,
        items=[{"product_id": seed["p2"].id, "quantity": 1, "unit_price": 5}],
    )
    inv.attachment_url = f"{seed['t2'].id}/purchase_invoices/beta.pdf"
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.get(f"/api/v1/purchasing/invoices/{inv.id}/attachment", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_backup_download_404(client, db_session, tmp_path, monkeypatch):
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
    r = await ac.get(f"/api/v1/backup/{job.id}/download", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_owned_expense_wrong_media_key_403(client, db_session):
    """Planted cross-tenant key on an owned row must not serve bytes."""
    ac, seed = client
    await ensure_default_categories(db_session, seed["t1"].id)
    await db_session.commit()
    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t1"].id)
        )
    ).scalars().all()
    expense = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["mgr1"].id,
        amount=9,
        description="Alpha with planted key",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    expense.attachment_url = f"{seed['t2'].id}/expenses/stolen.pdf"
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.get(f"/api/v1/expenses/{expense.id}/attachment", headers=headers)
    assert r.status_code == 403
    assert "tenant mismatch" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_owned_logo_wrong_media_key_403(client, db_session):
    ac, seed = client
    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    tenant.logo_url = f"{seed['t2'].id}/logos/stolen.png"
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.get("/api/v1/tenants/me/logo", headers=headers)
    assert r.status_code == 403
    assert "tenant mismatch" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_foreign_po_print_404(client, db_session):
    from app.purchasing import create_purchase_order

    ac, seed = client
    po = await create_purchase_order(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        supplier_id=seed["supplier2"].id,
        items=[{"product_id": seed["p2"].id, "quantity": 2, "unit_price": 3}],
    )
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.get(f"/api/v1/purchasing/orders/{po.id}/print", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_pos_receipt_404(client, db_session):
    ac, seed = client
    tx = m.Transaction(
        tenant_id=seed["t2"].id,
        tx_type="pos_sale",
        reference="POS-BETA-ISO-1",
        subtotal=10,
        tax=0,
        total=10,
        status="completed",
        payload={"items": []},
    )
    db_session.add(tx)
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.get(f"/api/v1/pos/sales/{tx.id}/receipt", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_product_labels_404(client):
    ac, seed = client
    headers = await _mgr_headers(ac)
    r = await ac.get(f"/api/v1/products/{seed['p2'].id}/labels", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_expense_ocr_suggest_404(client, db_session):
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
        amount=18,
        description="Beta OCR expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    expense.attachment_url = f"{seed['t2'].id}/expenses/beta-ocr.pdf"
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.post(f"/api/v1/expenses/{expense.id}/ocr-suggest", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_purchase_invoice_ocr_suggest_404(client, db_session):
    ac, seed = client
    inv = await create_purchase_invoice(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        supplier_id=seed["supplier2"].id,
        items=[{"product_id": seed["p2"].id, "quantity": 1, "unit_price": 4}],
    )
    inv.attachment_url = f"{seed['t2'].id}/purchase_invoices/beta-ocr.pdf"
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.post(f"/api/v1/purchasing/invoices/{inv.id}/ocr-suggest", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_pos_receipt_send_404(client, db_session):
    ac, seed = client
    tx = m.Transaction(
        tenant_id=seed["t2"].id,
        tx_type="pos_sale",
        reference="POS-BETA-SEND-1",
        subtotal=12,
        tax=0,
        total=12,
        status="completed",
        payload={"items": []},
    )
    db_session.add(tx)
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.post(
        f"/api/v1/pos/sales/{tx.id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": "nobody@example.com"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_account_id_on_bank_statement_import_404(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t2"].id)
    beta_bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    csv_text = "date,amount,description,ref\n2026-08-01,100,Deposit,D1\n"
    r = await ac.post(
        "/api/v1/accounting/bank-statements/import",
        headers=headers,
        params={"account_id": beta_bank.id, "opening_balance": 0},
        files={"file": ("beta.csv", csv_text, "text/csv")},
    )
    assert r.status_code == 404, r.text

    planted = (
        await db_session.execute(
            select(m.BankStatement).where(m.BankStatement.account_id == beta_bank.id)
        )
    ).scalars().all()
    assert planted == []


@pytest.mark.asyncio
async def test_foreign_account_id_on_bank_statement_create_404(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t2"].id)
    beta_bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": beta_bank.id,
            "statement_date": "2026-08-01",
            "opening_balance": 0,
            "closing_balance": 50,
            "lines": [{"posted_at": "2026-08-01", "amount": 50, "description": "x"}],
        },
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_foreign_account_id_on_bank_connection_create_404(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t2"].id)
    beta_bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": beta_bank.id,
            "provider": "mock",
            "display_name": "Hijack Beta Bank",
        },
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_foreign_warehouse_id_on_stock_in_404(client, db_session):
    ac, seed = client
    beta_wh = m.Warehouse(
        tenant_id=seed["t2"].id,
        name="Beta WH",
        code="BETA-WH",
    )
    db_session.add(beta_wh)
    await db_session.commit()

    headers = await _mgr_headers(ac)
    before = float(seed["p1"].stock_qty or 0)
    r = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": seed["p1"].id,
            "quantity": 3,
            "warehouse_id": beta_wh.id,
        },
    )
    assert r.status_code == 404, r.text

    await db_session.refresh(seed["p1"])
    assert float(seed["p1"].stock_qty or 0) == before
    leaked = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == beta_wh.id,
                m.WarehouseStock.tenant_id == seed["t1"].id,
            )
        )
    ).scalars().all()
    assert leaked == []


@pytest.mark.asyncio
async def test_foreign_liquid_account_id_on_customer_payment_404(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t2"].id)
    beta_bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.post(
        f"/api/v1/customers/{seed['party1'].id}/payments",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "amount": 5,
            "payment_method": "cash",
            "liquid_account_id": beta_bank.id,
        },
    )
    assert r.status_code == 404, r.text
    planted = (
        await db_session.execute(
            select(m.CustomerPayment).where(
                m.CustomerPayment.tenant_id == seed["t1"].id,
                m.CustomerPayment.liquid_account_id == beta_bank.id,
            )
        )
    ).scalars().all()
    assert planted == []


@pytest.mark.asyncio
async def test_foreign_liquid_account_id_on_supplier_payment_404(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t2"].id)
    beta_bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    supplier = m.Party(
        tenant_id=seed["t1"].id,
        name="Alpha Pay Supplier",
        kind="supplier",
        credit_limit=0,
        balance=20,
    )
    db_session.add(supplier)
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    r = await ac.post(
        f"/api/v1/suppliers/{supplier.id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "amount": 5,
            "payment_method": "bank_transfer",
            "liquid_account_id": beta_bank.id,
        },
    )
    assert r.status_code == 404, r.text
    planted = (
        await db_session.execute(
            select(m.SupplierPayment).where(
                m.SupplierPayment.tenant_id == seed["t1"].id,
                m.SupplierPayment.liquid_account_id == beta_bank.id,
            )
        )
    ).scalars().all()
    assert planted == []


@pytest.mark.asyncio
async def test_foreign_store_id_on_expense_create_404(client, db_session):
    ac, seed = client
    store = await create_store(
        db_session, tenant_id=seed["t2"].id, name="Beta Exp Store", code="BXS"
    )
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 4,
            "category": "General",
            "description": "Foreign store expense",
            "payment_method": "cash",
            "store_id": store.id,
        },
    )
    assert r.status_code == 404, r.text
    planted = (
        await db_session.execute(
            select(m.Expense).where(
                m.Expense.tenant_id == seed["t1"].id,
                m.Expense.store_id == store.id,
            )
        )
    ).scalars().all()
    assert planted == []


@pytest.mark.asyncio
async def test_foreign_manager_id_on_store_create_404(client, db_session):
    ac, seed = client
    headers = await _mgr_headers(ac)
    r = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "code": "MGR-X",
            "name": "Hijack Manager Store",
            "manager_id": seed["u2"].id,
        },
    )
    assert r.status_code == 404, r.text
    planted = (
        await db_session.execute(
            select(m.Store).where(
                m.Store.tenant_id == seed["t1"].id,
                m.Store.manager_id == seed["u2"].id,
            )
        )
    ).scalars().all()
    assert planted == []


@pytest.mark.asyncio
async def test_foreign_liquid_account_id_on_expense_create_404(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t2"].id)
    beta_bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t2"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 3,
            "category": "General",
            "description": "Foreign liquid GL expense",
            "payment_method": "cash",
            "liquid_account_id": beta_bank.id,
        },
    )
    assert r.status_code == 404, r.text
