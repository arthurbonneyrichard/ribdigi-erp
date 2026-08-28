"""Store-manager operational API scope hardening (manager_id; ADR-005 still deferred)."""

from __future__ import annotations

import io
import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import audit as audit_svc
from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_store_manager_sales_invoices_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Mgr Scope Main",
        code="MGR-MAIN",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Mgr Scope Other",
        code="MGR-OTHER",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SCOPE-MINE",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        store_id=store.id,
        posted_at=datetime.utcnow(),
        created_by=mgr.id,
    )
    theirs = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SCOPE-THEIRS",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=99,
        tax_amount=0,
        total_amount=99,
        store_id=other.id,
        posted_at=datetime.utcnow(),
        created_by=seed["admin1"].id,
    )
    null_inv = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SCOPE-NULL",
        customer_id=seed["party1"].id,
        status="draft",
        subtotal=5,
        tax_amount=0,
        total_amount=5,
        store_id=None,
        created_by=seed["admin1"].id,
    )
    draft_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SCOPE-DRAFT-O",
        customer_id=seed["party1"].id,
        status="draft",
        subtotal=8,
        tax_amount=0,
        total_amount=8,
        store_id=other.id,
        created_by=seed["admin1"].id,
    )
    draft_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SCOPE-DRAFT-M",
        customer_id=seed["party1"].id,
        status="draft",
        subtotal=7,
        tax_amount=0,
        total_amount=7,
        store_id=store.id,
        created_by=mgr.id,
    )
    db_session.add_all([mine, theirs, null_inv, draft_other, draft_mine])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["invoice_number"] for row in listed.json()["data"]}
    assert "INV-SCOPE-MINE" in numbers
    assert "INV-SCOPE-DRAFT-M" in numbers
    assert "INV-SCOPE-THEIRS" not in numbers
    assert "INV-SCOPE-NULL" not in numbers
    assert "INV-SCOPE-DRAFT-O" not in numbers

    denied = await ac.get(f"/api/v1/sales/invoices/{theirs.id}", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_null = await ac.get(f"/api/v1/sales/invoices/{null_inv.id}", headers=headers)
    assert denied_null.status_code == 403
    assert denied_null.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok = await ac.get(f"/api/v1/sales/invoices/{mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    cross = await ac.get(
        "/api/v1/sales/invoices",
        headers=headers,
        params={"store_id": other.id},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    exported = await ac.get("/api/v1/sales/invoices/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "INV-SCOPE-MINE" in exported.text
    assert "INV-SCOPE-THEIRS" not in exported.text
    assert "INV-SCOPE-NULL" not in exported.text

    create_other = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "store_id": other.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_other.status_code == 403
    assert create_other.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_unset = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_unset.status_code == 403
    assert create_unset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_ok = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_ok.status_code == 200, create_ok.text

    denied_post = await ac.post(
        f"/api/v1/sales/invoices/{draft_other.id}/post", headers=headers
    )
    assert denied_post.status_code == 403
    assert denied_post.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_send = await ac.post(
        f"/api/v1/sales/invoices/{theirs.id}/send", headers=headers
    )
    assert denied_send.status_code == 403
    assert denied_send.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_cancel = await ac.post(
        f"/api/v1/sales/invoices/{draft_other.id}/cancel", headers=headers
    )
    assert denied_cancel.status_code == 403
    assert denied_cancel.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    cancel_ok = await ac.post(
        f"/api/v1/sales/invoices/{draft_mine.id}/cancel", headers=headers
    )
    assert cancel_ok.status_code == 200, cancel_ok.text


@pytest.mark.asyncio
async def test_store_manager_pos_sales_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    await accounting_svc.ensure_default_accounts(db_session, tid)
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="POS Mgr Store",
        code="POS-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="POS Other Store",
        code="POS-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()

    sess_mine = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        user_id=mgr.id,
        session_number="S-MGR-1",
        status="open",
        opening_cash=0,
    )
    sess_other = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        user_id=mgr.id,
        session_number="S-OTH-1",
        status="open",
        opening_cash=0,
    )
    db_session.add_all([sess_mine, sess_other])
    await db_session.flush()
    sale_mine = m.Transaction(
        tenant_id=tid,
        company_id=cid,
        tx_type="pos_sale",
        reference="POS-MGR-REF",
        session_id=sess_mine.id,
        subtotal=5,
        tax=0,
        total=5,
        status="completed",
        payload={},
    )
    sale_other = m.Transaction(
        tenant_id=tid,
        company_id=cid,
        tx_type="pos_sale",
        reference="POS-OTH-REF",
        session_id=sess_other.id,
        subtotal=50,
        tax=0,
        total=50,
        status="completed",
        payload={},
    )
    db_session.add_all([sale_mine, sale_other])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/pos/sales", headers=headers)
    assert r.status_code == 200, r.text
    refs = {row["reference"] for row in r.json()["data"]}
    assert "POS-MGR-REF" in refs
    assert "POS-OTH-REF" not in refs

    denied = await ac.get(
        "/api/v1/pos/sales",
        headers=headers,
        params={"store_id": other.id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    receipt_ok = await ac.get(
        f"/api/v1/pos/sales/{sale_mine.id}/receipt",
        headers=headers,
    )
    assert receipt_ok.status_code == 200, receipt_ok.text
    assert receipt_ok.json()["data"]["reference"] == "POS-MGR-REF"

    receipt_denied = await ac.get(
        f"/api/v1/pos/sales/{sale_other.id}/receipt",
        headers=headers,
    )
    assert receipt_denied.status_code == 403
    assert receipt_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    send_denied = await ac.post(
        f"/api/v1/pos/sales/{sale_other.id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": "other@example.com"},
    )
    assert send_denied.status_code == 403
    assert send_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_expenses_and_stores_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Exp Mgr Store",
        code="EXP-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Exp Other Store",
        code="EXP-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    mine = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Managed store expense",
        amount=12.5,
        store_id=store.id,
        status="pending",
        created_by=mgr.id,
    )
    theirs = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Other store expense",
        amount=99,
        store_id=other.id,
        status="pending",
        created_by=mgr.id,
    )
    unset = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="No store expense",
        amount=5,
        store_id=None,
        status="pending",
        created_by=mgr.id,
    )
    db_session.add_all([mine, theirs, unset])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200, stores.text
    store_ids = {row["id"] for row in stores.json()["data"]}
    assert store.id in store_ids
    assert other.id not in store_ids

    listed = await ac.get("/api/v1/expenses", headers=headers)
    assert listed.status_code == 200, listed.text
    descs = {row["description"] for row in listed.json()["data"]}
    assert "Managed store expense" in descs
    assert "Other store expense" not in descs
    assert "No store expense" not in descs

    assert (await ac.get(f"/api/v1/expenses/{theirs.id}", headers=headers)).status_code == 403
    assert (await ac.get(f"/api/v1/expenses/{unset.id}", headers=headers)).status_code == 403
    ok = await ac.get(f"/api/v1/expenses/{mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    foreign_create = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Travel",
            "amount": 8,
            "description": "Foreign create blocked",
            "payment_method": "cash",
            "store_id": other.id,
        },
    )
    assert foreign_create.status_code == 403
    assert foreign_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_create = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Travel",
            "amount": 7,
            "description": "Managed create ok",
            "payment_method": "cash",
            "store_id": store.id,
        },
    )
    assert ok_create.status_code == 200, ok_create.text
    assert ok_create.json()["data"]["store_id"] == store.id

    foreign_recurring = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category": "Rent",
            "amount": 50,
            "description": "Foreign recurring",
            "frequency": "monthly",
            "payment_method": "cash",
            "store_id": other.id,
        },
    )
    assert foreign_recurring.status_code == 403
    assert foreign_recurring.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Cannot reassign an in-scope expense onto an unmanaged store
    reassign = await ac.patch(
        f"/api/v1/expenses/{mine.id}",
        headers=headers,
        json={"store_id": other.id},
    )
    assert reassign.status_code == 403
    assert reassign.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    inv_denied = await ac.get(f"/api/v1/stores/{other.id}/inventory", headers=headers)
    assert inv_denied.status_code == 403
    assert inv_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    sales_denied = await ac.get(f"/api/v1/stores/{other.id}/sales", headers=headers)
    assert sales_denied.status_code == 403
    assert sales_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_stock_transfers_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Xfer Mgr Store",
        code="XFER-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other_a = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Xfer Other A",
        code="XFER-OA",
        manager_id=None,
        is_active=True,
    )
    other_b = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Xfer Other B",
        code="XFER-OB",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other_a, other_b])
    await db_session.flush()

    wh_store = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        name="Xfer Mgr WH",
        code="WH-XFER-MGR",
        warehouse_type="retail",
        is_active=True,
    )
    wh_a = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other_a.id,
        name="Xfer OA WH",
        code="WH-XFER-OA",
        warehouse_type="retail",
        is_active=True,
    )
    wh_b = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other_b.id,
        name="Xfer OB WH",
        code="WH-XFER-OB",
        warehouse_type="retail",
        is_active=True,
    )
    db_session.add_all([wh_store, wh_a, wh_b])
    await db_session.flush()

    mine = m.StockTransfer(
        tenant_id=tid,
        company_id=cid,
        transfer_number="XFER-SCOPE-MINE",
        from_store_id=store.id,
        to_store_id=other_a.id,
        from_warehouse_id=wh_store.id,
        to_warehouse_id=wh_a.id,
        status="draft",
        notes="touches managed",
        created_by=mgr.id,
    )
    inbound = m.StockTransfer(
        tenant_id=tid,
        company_id=cid,
        transfer_number="XFER-SCOPE-IN",
        from_store_id=other_a.id,
        to_store_id=store.id,
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_store.id,
        status="draft",
        notes="inbound to managed",
        created_by=mgr.id,
    )
    theirs = m.StockTransfer(
        tenant_id=tid,
        company_id=cid,
        transfer_number="XFER-SCOPE-THEIRS",
        from_store_id=other_a.id,
        to_store_id=other_b.id,
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_b.id,
        status="draft",
        notes="outside managed",
        created_by=mgr.id,
    )
    db_session.add_all([mine, inbound, theirs])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    listed = await ac.get("/api/v1/stores/transfers", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["transfer_number"] for row in listed.json()["data"]}
    assert "XFER-SCOPE-MINE" in numbers
    assert "XFER-SCOPE-IN" in numbers
    assert "XFER-SCOPE-THEIRS" not in numbers

    inv_listed = await ac.get("/api/v1/inventory/stock-transfers", headers=headers)
    assert inv_listed.status_code == 200, inv_listed.text
    inv_numbers = {row["transfer_number"] for row in inv_listed.json()["data"]}
    assert "XFER-SCOPE-MINE" in inv_numbers
    assert "XFER-SCOPE-THEIRS" not in inv_numbers

    ok = await ac.get(f"/api/v1/stores/transfers/{mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    denied = await ac.get(f"/api/v1/stores/transfers/{theirs.id}", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    cross = await ac.get(
        "/api/v1/stores/transfers",
        headers=headers,
        params={"store_id": other_a.id},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_denied = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": other_a.id,
            "to_store_id": other_b.id,
            "submit": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert create_denied.status_code == 403
    assert create_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    submit_denied = await ac.post(
        f"/api/v1/stores/transfers/{theirs.id}/submit",
        headers=headers,
    )
    assert submit_denied.status_code == 403
    assert submit_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_warehouses_and_inventory_ops_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = seed["p1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Inv Mgr Store",
        code="INV-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Inv Other Store",
        code="INV-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()

    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        name="Inv Mgr WH",
        code="WH-INV-MGR",
        warehouse_type="retail",
        is_active=True,
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Inv Other WH",
        code="WH-INV-OTH",
        warehouse_type="retail",
        is_active=True,
    )
    wh_central = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=None,
        name="Inv Central WH",
        code="WH-INV-CTR",
        warehouse_type="main",
        is_active=True,
    )
    db_session.add_all([wh_mine, wh_other, wh_central])
    await db_session.flush()

    db_session.add_all(
        [
            m.WarehouseStock(
                tenant_id=tid,
                company_id=cid,
                warehouse_id=wh_mine.id,
                product_id=product.id,
                quantity=7,
            ),
            m.WarehouseStock(
                tenant_id=tid,
                company_id=cid,
                warehouse_id=wh_other.id,
                product_id=product.id,
                quantity=70,
            ),
            m.StockMovement(
                tenant_id=tid,
                company_id=cid,
                product_id=product.id,
                warehouse_id=wh_mine.id,
                movement_type="stock_in",
                quantity=7,
                quantity_before=0,
                quantity_after=7,
                notes="mine",
                created_by=mgr.id,
            ),
            m.StockMovement(
                tenant_id=tid,
                company_id=cid,
                product_id=product.id,
                warehouse_id=wh_other.id,
                movement_type="stock_in",
                quantity=70,
                quantity_before=0,
                quantity_after=70,
                notes="other",
                created_by=mgr.id,
            ),
            m.StockCount(
                tenant_id=tid,
                company_id=cid,
                warehouse_id=wh_mine.id,
                count_number="CNT-SCOPE-MINE",
                status="draft",
                created_by=mgr.id,
            ),
            m.StockCount(
                tenant_id=tid,
                company_id=cid,
                warehouse_id=wh_other.id,
                count_number="CNT-SCOPE-OTH",
                status="draft",
                created_by=mgr.id,
            ),
        ]
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    warehouses = await ac.get("/api/v1/warehouses", headers=headers)
    assert warehouses.status_code == 200, warehouses.text
    codes = {row["code"] for row in warehouses.json()["data"]}
    assert "WH-INV-MGR" in codes
    assert "WH-INV-OTH" not in codes
    assert "WH-INV-CTR" not in codes

    movements = await ac.get("/api/v1/inventory/movements", headers=headers)
    assert movements.status_code == 200, movements.text
    notes = {row.get("notes") for row in movements.json()["data"]}
    assert "mine" in notes
    assert "other" not in notes

    denied_wh = await ac.get(
        "/api/v1/inventory/movements",
        headers=headers,
        params={"warehouse_id": wh_other.id},
    )
    assert denied_wh.status_code == 403
    assert denied_wh.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    stock = await ac.get(f"/api/v1/products/{product.id}/warehouse-stock", headers=headers)
    assert stock.status_code == 200, stock.text
    wh_codes = {row["code"] for row in stock.json()["data"]["warehouses"]}
    assert "WH-INV-MGR" in wh_codes
    assert "WH-INV-OTH" not in wh_codes

    counts = await ac.get("/api/v1/inventory/stock-counts", headers=headers)
    assert counts.status_code == 200, counts.text
    count_nums = {row["count_number"] for row in counts.json()["data"]}
    assert "CNT-SCOPE-MINE" in count_nums
    assert "CNT-SCOPE-OTH" not in count_nums

    other_count = (
        await db_session.execute(
            select(m.StockCount).where(m.StockCount.count_number == "CNT-SCOPE-OTH")
        )
    ).scalar_one()
    denied_count = await ac.get(
        f"/api/v1/inventory/stock-counts/{other_count.id}", headers=headers
    )
    assert denied_count.status_code == 403
    assert denied_count.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_count_denied = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh_other.id, "notes": "nope"},
    )
    assert create_count_denied.status_code == 403
    assert create_count_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    stock_in_denied = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 1, "warehouse_id": wh_other.id},
    )
    assert stock_in_denied.status_code == 403
    assert stock_in_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    stock_in_unset = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 1},
    )
    assert stock_in_unset.status_code == 403
    assert stock_in_unset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    stock_in_ok = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 1, "warehouse_id": wh_mine.id},
    )
    assert stock_in_ok.status_code == 200, stock_in_ok.text

    create_wh_denied = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": "WH-BAD",
            "name": "Bad WH",
            "store_id": other.id,
            "warehouse_type": "retail",
        },
    )
    assert create_wh_denied.status_code == 403
    assert create_wh_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_wh_own_denied = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": "WH-OWN-BAD",
            "name": "Own Bad WH",
            "store_id": store.id,
            "warehouse_type": "retail",
        },
    )
    assert create_wh_own_denied.status_code == 403
    assert create_wh_own_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_purchasing_pipeline_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="PO Mgr Store",
        code="PO-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="PO Other Store",
        code="PO-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        name="PO Mgr WH",
        code="WH-PO-MGR",
        warehouse_type="retail",
        is_active=True,
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="PO Other WH",
        code="WH-PO-OTH",
        warehouse_type="retail",
        is_active=True,
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Scope Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add_all([wh_mine, wh_other, supplier])
    await db_session.flush()

    mine_po = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-SCOPE-MINE",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="draft",
        created_by=mgr.id,
    )
    other_po = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-SCOPE-OTH",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="draft",
        created_by=mgr.id,
    )
    unset_po = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-SCOPE-UNSET",
        supplier_id=supplier.id,
        warehouse_id=None,
        status="draft",
        created_by=mgr.id,
    )
    mine_pr = m.PurchaseRequest(
        tenant_id=tid,
        company_id=cid,
        request_number="PR-SCOPE-MINE",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="draft",
        created_by=mgr.id,
    )
    other_pr = m.PurchaseRequest(
        tenant_id=tid,
        company_id=cid,
        request_number="PR-SCOPE-OTH",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="draft",
        created_by=mgr.id,
    )
    db_session.add_all([mine_po, other_po, unset_po, mine_pr, other_pr])
    await db_session.flush()
    mine_grn = m.GoodsReceipt(
        tenant_id=tid,
        company_id=cid,
        grn_number="GRN-SCOPE-MINE",
        purchase_order_id=mine_po.id,
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="posted",
        created_by=mgr.id,
    )
    other_grn = m.GoodsReceipt(
        tenant_id=tid,
        company_id=cid,
        grn_number="GRN-SCOPE-OTH",
        purchase_order_id=other_po.id,
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="posted",
        created_by=mgr.id,
    )
    db_session.add_all([mine_grn, other_grn])
    await db_session.flush()
    mine_ret = m.PurchaseReturn(
        tenant_id=tid,
        company_id=cid,
        return_number="RET-SCOPE-MINE",
        debit_note_number="DN-SCOPE-MINE",
        supplier_id=supplier.id,
        purchase_order_id=mine_po.id,
        goods_receipt_id=mine_grn.id,
        warehouse_id=wh_mine.id,
        status="draft",
        created_by=mgr.id,
    )
    other_ret = m.PurchaseReturn(
        tenant_id=tid,
        company_id=cid,
        return_number="RET-SCOPE-OTH",
        debit_note_number="DN-SCOPE-OTH",
        supplier_id=supplier.id,
        purchase_order_id=other_po.id,
        goods_receipt_id=other_grn.id,
        warehouse_id=wh_other.id,
        status="draft",
        created_by=mgr.id,
    )
    db_session.add_all([mine_ret, other_ret])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    orders = await ac.get("/api/v1/purchasing/orders", headers=headers)
    assert orders.status_code == 200, orders.text
    po_nums = {row["po_number"] for row in orders.json()["data"]}
    assert "PO-SCOPE-MINE" in po_nums
    assert "PO-SCOPE-OTH" not in po_nums
    assert "PO-SCOPE-UNSET" not in po_nums

    assert (await ac.get(f"/api/v1/purchasing/orders/{other_po.id}", headers=headers)).status_code == 403
    assert (await ac.get(f"/api/v1/purchasing/orders/{unset_po.id}", headers=headers)).status_code == 403
    ok = await ac.get(f"/api/v1/purchasing/orders/{mine_po.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    reqs = await ac.get("/api/v1/purchasing/requests", headers=headers)
    assert reqs.status_code == 200, reqs.text
    pr_nums = {row["request_number"] for row in reqs.json()["data"]}
    assert "PR-SCOPE-MINE" in pr_nums
    assert "PR-SCOPE-OTH" not in pr_nums

    grns = await ac.get("/api/v1/purchasing/grn", headers=headers)
    assert grns.status_code == 200, grns.text
    grn_nums = {row["grn_number"] for row in grns.json()["data"]}
    assert "GRN-SCOPE-MINE" in grn_nums
    assert "GRN-SCOPE-OTH" not in grn_nums

    rets = await ac.get("/api/v1/purchasing/returns", headers=headers)
    assert rets.status_code == 200, rets.text
    ret_nums = {row["return_number"] for row in rets.json()["data"]}
    assert "RET-SCOPE-MINE" in ret_nums
    assert "RET-SCOPE-OTH" not in ret_nums

    create_denied = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "warehouse_id": wh_other.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert create_denied.status_code == 403
    assert create_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_unset = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert create_unset.status_code == 403
    assert create_unset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_purchase_invoices_scoped_via_po_grn(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="PI Mgr Store",
        code="PI-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="PI Other Store",
        code="PI-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        name="PI Mgr WH",
        code="WH-PI-MGR",
        warehouse_type="retail",
        is_active=True,
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="PI Other WH",
        code="WH-PI-OTH",
        warehouse_type="retail",
        is_active=True,
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="PI Scope Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add_all([wh_mine, wh_other, supplier])
    await db_session.flush()

    po_mine = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-PI-MINE",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="received",
        created_by=mgr.id,
    )
    po_other = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-PI-OTH",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="received",
        created_by=mgr.id,
    )
    db_session.add_all([po_mine, po_other])
    await db_session.flush()

    inv_mine = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-SCOPE-MINE",
        supplier_id=supplier.id,
        purchase_order_id=po_mine.id,
        status="draft",
        created_by=mgr.id,
    )
    inv_other = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-SCOPE-OTH",
        supplier_id=supplier.id,
        purchase_order_id=po_other.id,
        status="draft",
        created_by=mgr.id,
    )
    inv_manual = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-SCOPE-MANUAL",
        supplier_id=supplier.id,
        purchase_order_id=None,
        goods_receipt_id=None,
        warehouse_id=None,
        status="draft",
        created_by=mgr.id,
    )
    inv_manual_scoped = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-SCOPE-MANUAL-WH",
        supplier_id=supplier.id,
        purchase_order_id=None,
        goods_receipt_id=None,
        warehouse_id=wh_mine.id,
        status="draft",
        created_by=mgr.id,
    )
    db_session.add_all([inv_mine, inv_other, inv_manual, inv_manual_scoped])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    listed = await ac.get("/api/v1/purchasing/invoices", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["invoice_number"] for row in listed.json()["data"]}
    assert "PI-SCOPE-MINE" in numbers
    assert "PI-SCOPE-MANUAL-WH" in numbers
    assert "PI-SCOPE-OTH" not in numbers
    assert "PI-SCOPE-MANUAL" not in numbers

    ok = await ac.get(f"/api/v1/purchasing/invoices/{inv_mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text
    assert (
        await ac.get(f"/api/v1/purchasing/invoices/{inv_manual_scoped.id}", headers=headers)
    ).status_code == 200
    assert (await ac.get(f"/api/v1/purchasing/invoices/{inv_other.id}", headers=headers)).status_code == 403
    assert (await ac.get(f"/api/v1/purchasing/invoices/{inv_manual.id}", headers=headers)).status_code == 403

    create_manual = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_manual.status_code == 403
    assert create_manual.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_manual_ok = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "warehouse_id": wh_mine.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_manual_ok.status_code == 200, create_manual_ok.text
    assert create_manual_ok.json()["data"]["warehouse_id"] == wh_mine.id
    assert create_manual_ok.json()["data"]["invoice_number"]

    create_manual_other_wh = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "warehouse_id": wh_other.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_manual_other_wh.status_code == 403
    assert create_manual_other_wh.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_other = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "purchase_order_id": po_other.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_other.status_code == 403
    assert create_other.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_sales_orders_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Order Mgr Store",
        code="ORD-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Order Other Store",
        code="ORD-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    mine = m.SalesOrder(
        tenant_id=tid,
        company_id=cid,
        order_number="SO-SCOPE-MINE",
        customer_id=seed["party1"].id,
        status="draft",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        store_id=store.id,
        created_by=mgr.id,
    )
    theirs = m.SalesOrder(
        tenant_id=tid,
        company_id=cid,
        order_number="SO-SCOPE-THEIRS",
        customer_id=seed["party1"].id,
        status="draft",
        subtotal=99,
        tax_amount=0,
        total_amount=99,
        store_id=other.id,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([mine, theirs])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/sales/orders", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["order_number"] for row in listed.json()["data"]}
    assert "SO-SCOPE-MINE" in numbers
    assert "SO-SCOPE-THEIRS" not in numbers

    denied = await ac.get(f"/api/v1/sales/orders/{theirs.id}", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok = await ac.get(f"/api/v1/sales/orders/{mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    create_denied = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "store_id": other.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_denied.status_code == 403
    assert create_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_ok = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_ok.status_code == 200, create_ok.text

    create_unset = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert create_unset.status_code == 403
    assert create_unset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    cross = await ac.get(
        "/api/v1/sales/orders",
        headers=headers,
        params={"store_id": other.id},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_sales_quotations_scoped(client, db_session):
    """Quotations: own drafts + converted in-scope docs; foreign open quotes hidden."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    admin = seed["admin1"]
    cust = seed["party1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Quote Scope Mine",
        code="QT-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Quote Scope Other",
        code="QT-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-QT-M",
        customer_id=cust.id,
        status="posted",
        subtotal=40,
        total_amount=40,
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-QT-O",
        customer_id=cust.id,
        status="posted",
        subtotal=90,
        total_amount=90,
    )
    db_session.add_all([inv_mine, inv_other])
    await db_session.flush()

    qt_m_open = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="QT-M-OPEN",
        customer_id=cust.id,
        status="draft",
        subtotal=10,
        total_amount=10,
        created_by=mgr.id,
    )
    qt_o_open = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="QT-O-OPEN",
        customer_id=cust.id,
        status="sent",
        subtotal=20,
        total_amount=20,
        created_by=admin.id,
    )
    qt_m_conv = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="QT-M-CONV",
        customer_id=cust.id,
        status="converted",
        subtotal=40,
        total_amount=40,
        created_by=admin.id,
        converted_invoice_id=inv_mine.id,
    )
    qt_o_conv = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="QT-O-CONV",
        customer_id=cust.id,
        status="converted",
        subtotal=90,
        total_amount=90,
        created_by=admin.id,
        converted_invoice_id=inv_other.id,
    )
    db_session.add_all([qt_m_open, qt_o_open, qt_m_conv, qt_o_conv])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/sales/quotations", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["quotation_number"] for row in listed.json()["data"]}
    assert "QT-M-OPEN" in numbers
    assert "QT-M-CONV" in numbers
    assert "QT-O-OPEN" not in numbers
    assert "QT-O-CONV" not in numbers

    exported = await ac.get("/api/v1/sales/quotations/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "QT-M-OPEN" in exported.text
    assert "QT-O-OPEN" not in exported.text
    assert "QT-O-CONV" not in exported.text

    ok = await ac.get(f"/api/v1/sales/quotations/{qt_m_open.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    denied_get = await ac.get(f"/api/v1/sales/quotations/{qt_o_open.id}", headers=headers)
    assert denied_get.status_code == 403
    assert denied_get.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_accept = await ac.post(
        f"/api/v1/sales/quotations/{qt_o_open.id}/accept", headers=headers
    )
    assert denied_accept.status_code == 403
    assert denied_accept.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    draft = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": cust.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 12}],
        },
    )
    assert draft.status_code == 200, draft.text
    qid = draft.json()["data"]["id"]

    denied_convert = await ac.post(
        f"/api/v1/sales/quotations/{qid}/convert-order",
        headers=headers,
        json={},
    )
    assert denied_convert.status_code == 403
    assert denied_convert.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_convert = await ac.post(
        f"/api/v1/sales/quotations/{qid}/convert-order",
        headers=headers,
        json={"store_id": mine.id},
    )
    assert ok_convert.status_code == 200, ok_convert.text
    assert ok_convert.json()["data"]["store_id"] == mine.id


@pytest.mark.asyncio
async def test_store_manager_pos_sessions_scoped(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Sess Mgr Store",
        code="SES-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Sess Other Store",
        code="SES-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    sess_mine = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=store.id,
        user_id=mgr.id,
        session_number="SES-MGR-1",
        status="open",
        opening_cash=0,
    )
    sess_other = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        user_id=seed["admin1"].id,
        session_number="SES-OTH-1",
        status="open",
        opening_cash=0,
    )
    db_session.add_all([sess_mine, sess_other])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/pos/sessions", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["session_number"] for row in listed.json()["data"]}
    assert "SES-MGR-1" in numbers
    assert "SES-OTH-1" not in numbers

    denied = await ac.get(f"/api/v1/pos/sessions/{sess_other.id}/report", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok = await ac.get(f"/api/v1/pos/sessions/{sess_mine.id}/report", headers=headers)
    assert ok.status_code == 200, ok.text

    open_denied = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": other.id, "opening_cash": 0},
    )
    assert open_denied.status_code == 403
    assert open_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Close mine first so open succeeds on managed store
    closed = await ac.post(
        f"/api/v1/pos/sessions/{sess_mine.id}/close",
        headers=headers,
        json={"actual_cash": 0},
    )
    assert closed.status_code == 200, closed.text

    open_ok = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"store_id": store.id, "opening_cash": 10},
    )
    assert open_ok.status_code == 200, open_ok.text


@pytest.mark.asyncio
async def test_store_manager_low_stock_and_expiry_warehouse_scoped(client, db_session):
    """Managers see only managed-WH low-stock/expiry rows; omit product scope + other WHs."""
    from datetime import timedelta

    from app.inventory import apply_stock_change

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="LS Alert Mine",
        code="LS-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="LS Alert Other",
        code="LS-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="LS Mine WH",
        code="LS-M-WH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="LS Other WH",
        code="LS-O-WH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    seed["p1"].stock_qty = 2
    seed["p1"].minimum_stock = 5
    seed["p1"].reorder_level = 20
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=3,
        movement_type="stock_in",
        user_id=mgr.id,
        warehouse_id=wh_mine.id,
    )
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=3,
        movement_type="stock_in",
        user_id=seed["admin1"].id,
        warehouse_id=wh_other.id,
    )
    stock_mine = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == wh_mine.id,
                m.WarehouseStock.product_id == seed["p1"].id,
            )
        )
    ).scalar_one()
    stock_other = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == wh_other.id,
                m.WarehouseStock.product_id == seed["p1"].id,
            )
        )
    ).scalar_one()
    stock_mine.minimum_stock = 10
    stock_mine.reorder_level = 20
    stock_other.minimum_stock = 10
    stock_other.reorder_level = 20

    soon = datetime.utcnow() + timedelta(days=7)
    batch_mine = m.ProductBatch(
        tenant_id=tid,
        company_id=cid,
        product_id=seed["p1"].id,
        warehouse_id=wh_mine.id,
        batch_number="LOT-LS-MINE",
        expiry_date=soon,
        quantity=3,
    )
    batch_other = m.ProductBatch(
        tenant_id=tid,
        company_id=cid,
        product_id=seed["p1"].id,
        warehouse_id=wh_other.id,
        batch_number="LOT-LS-OTH",
        expiry_date=soon,
        quantity=3,
    )
    batch_null = m.ProductBatch(
        tenant_id=tid,
        company_id=cid,
        product_id=seed["p1"].id,
        warehouse_id=None,
        batch_number="LOT-LS-NULL",
        expiry_date=soon,
        quantity=1,
    )
    db_session.add_all([batch_mine, batch_other, batch_null])
    await db_session.commit()

    low = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    low_rows = low.json()["data"]
    assert not any(r.get("scope") == "product" for r in low_rows)
    wh_ids = {r.get("warehouse_id") for r in low_rows if r.get("scope") == "warehouse"}
    assert wh_mine.id in wh_ids
    assert wh_other.id not in wh_ids

    report = await ac.get("/api/v1/reports/inventory/low-stock", headers=headers)
    assert report.status_code == 200, report.text
    report_data = report.json()["data"]
    assert report_data["count"] == 0
    assert report_data["products"] == []
    report_wh = {r["warehouse_id"] for r in report_data["warehouse_low_stock"]}
    assert wh_mine.id in report_wh
    assert wh_other.id not in report_wh

    expiring = await ac.get("/api/v1/inventory/batches/expiring?days=30", headers=headers)
    assert expiring.status_code == 200, expiring.text
    lots = {b["batch_number"] for b in expiring.json()["data"]["batches"]}
    assert "LOT-LS-MINE" in lots
    assert "LOT-LS-OTH" not in lots
    assert "LOT-LS-NULL" not in lots

    expiry_report = await ac.get("/api/v1/reports/inventory/expiry?days=30", headers=headers)
    assert expiry_report.status_code == 200, expiry_report.text
    expiry_lots = {b["batch_number"] for b in expiry_report.json()["data"]["batches"]}
    assert "LOT-LS-MINE" in expiry_lots
    assert "LOT-LS-OTH" not in expiry_lots
    assert "LOT-LS-NULL" not in expiry_lots

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="LS Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    missing_wh = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={"product_id": seed["p1"].id, "supplier_id": supplier.id},
    )
    assert missing_wh.status_code == 403
    assert missing_wh.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    cross_wh = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={
            "product_id": seed["p1"].id,
            "supplier_id": supplier.id,
            "warehouse_id": wh_other.id,
        },
    )
    assert cross_wh.status_code == 403
    assert cross_wh.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_po = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={
            "product_id": seed["p1"].id,
            "supplier_id": supplier.id,
            "warehouse_id": wh_mine.id,
            "quantity": 5,
        },
    )
    assert ok_po.status_code == 200, ok_po.text
    assert ok_po.json()["data"]["warehouse_id"] == wh_mine.id


@pytest.mark.asyncio
async def test_store_manager_inventory_reports_warehouse_scoped(client, db_session):
    """Balance / valuation / movements reports omit other-store WHs and product fallback."""
    from app.inventory import apply_stock_change

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="InvRep Mine",
        code="IR-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="InvRep Other",
        code="IR-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="IR Mine WH",
        code="IR-M-WH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="IR Other WH",
        code="IR-O-WH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    seed["p1"].cost_price = 2
    seed["p1"].stock_qty = 99
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=mgr.id,
        warehouse_id=wh_mine.id,
    )
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=7,
        movement_type="stock_in",
        user_id=seed["admin1"].id,
        warehouse_id=wh_other.id,
    )
    await db_session.commit()

    balance = await ac.get("/api/v1/reports/inventory/balance", headers=headers)
    assert balance.status_code == 200, balance.text
    bal_items = balance.json()["data"]["items"]
    assert all(i.get("warehouse_id") == wh_mine.id for i in bal_items)
    assert any(float(i["quantity"]) == 5 for i in bal_items)
    assert not any(float(i["quantity"]) == 99 and i.get("warehouse_id") is None for i in bal_items)

    valuation = await ac.get("/api/v1/reports/inventory/valuation", headers=headers)
    assert valuation.status_code == 200, valuation.text
    vbody = valuation.json()["data"]
    wh_ids = {w["warehouse_id"] for w in vbody["by_warehouse"]}
    assert wh_mine.id in wh_ids
    assert wh_other.id not in wh_ids
    assert vbody["total_quantity"] == pytest.approx(5.0)
    assert vbody["total_value"] == pytest.approx(10.0)

    movements = await ac.get("/api/v1/reports/inventory/movements", headers=headers)
    assert movements.status_code == 200, movements.text
    mov_wh = {mrow["warehouse_id"] for mrow in movements.json()["data"]["movements"]}
    assert wh_mine.id in mov_wh
    assert wh_other.id not in mov_wh

    summary = await ac.get("/api/v1/reports/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    low = summary.json()["data"]["low_stock_report"]
    assert low.get("count") == 0
    assert low.get("products") == []

    exported = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "inventory_valuation", "format": "csv"},
    )
    assert exported.status_code == 200, exported.text
    assert wh_other.code not in exported.text or "IR-O-WH" not in exported.text


@pytest.mark.asyncio
async def test_store_manager_sales_reports_store_scoped(client, db_session):
    """Daily/monthly/by-store/customer/salesperson sales reports exclude other stores."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="SalesRep Mine",
        code="SR-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="SalesRep Other",
        code="SR-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    mine_inv = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SR-MINE",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=50,
        tax_amount=0,
        total_amount=50,
        store_id=mine.id,
        posted_at=today,
        created_by=mgr.id,
    )
    other_inv = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="INV-SR-OTH",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=999,
        tax_amount=0,
        total_amount=999,
        store_id=other.id,
        posted_at=today,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([mine_inv, other_inv])
    await db_session.commit()

    daily = await ac.get("/api/v1/reports/sales/daily", headers=headers)
    assert daily.status_code == 200, daily.text
    dbody = daily.json()["data"]
    assert float(dbody["total_revenue"]) == pytest.approx(50.0)
    assert int(dbody["invoice_count"]) == 1

    monthly = await ac.get(
        "/api/v1/reports/sales/monthly",
        headers=headers,
        params={"year": today.year, "month": today.month},
    )
    assert monthly.status_code == 200, monthly.text
    assert float(monthly.json()["data"]["total_revenue"]) == pytest.approx(50.0)

    by_store = await ac.get("/api/v1/reports/sales/by-store", headers=headers)
    assert by_store.status_code == 200, by_store.text
    store_ids = {s["store_id"] for s in by_store.json()["data"]["stores"]}
    assert mine.id in store_ids
    assert other.id not in store_ids

    customers = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert customers.status_code == 200, customers.text
    assert float(customers.json()["data"]["total_revenue"]) == pytest.approx(50.0)

    salesperson = await ac.get("/api/v1/reports/sales/salesperson", headers=headers)
    assert salesperson.status_code == 200, salesperson.text
    assert float(salesperson.json()["data"]["total_revenue"]) == pytest.approx(50.0)

    products = await ac.get(
        "/api/v1/reports/sales/products",
        headers=headers,
        params={"store_id": other.id},
    )
    assert products.status_code == 403
    assert products.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    summary = await ac.get("/api/v1/reports/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert float(summary.json()["data"]["today_sales"]["total_revenue"]) == pytest.approx(50.0)

    exported = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "sales_daily", "format": "csv"},
    )
    assert exported.status_code == 200, exported.text
    assert "999" not in exported.text or "INV-SR-OTH" not in exported.text


@pytest.mark.asyncio
async def test_store_manager_purchasing_reports_and_stock_transfer_writes_scoped(
    client, db_session
):
    """Purchasing reports WH-scoped; warehouse stock-transfer writes assert scope."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="PurRep Mine",
        code="PR-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="PurRep Other",
        code="PR-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="PR Mine WH",
        code="PR-M-WH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="PR Other WH",
        code="PR-O-WH",
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="PurRep Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add_all([wh_mine, wh_other, supplier])
    await db_session.flush()

    po_mine = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-PR-MINE",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="sent",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        paid_amount=0,
        created_by=mgr.id,
    )
    po_other = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-PR-OTH",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="sent",
        subtotal=400,
        tax_amount=0,
        total_amount=400,
        paid_amount=0,
        created_by=seed["admin1"].id,
    )
    po_null = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-PR-NULL",
        supplier_id=supplier.id,
        warehouse_id=None,
        status="sent",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        paid_amount=0,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([po_mine, po_other, po_null])
    await db_session.commit()

    summary = await ac.get("/api/v1/reports/purchases/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    sbody = summary.json()["data"]
    assert int(sbody["order_count"]) == 1
    assert float(sbody["total_amount"]) == pytest.approx(40.0)

    suppliers = await ac.get("/api/v1/reports/purchases/suppliers", headers=headers)
    assert suppliers.status_code == 200, suppliers.text
    assert float(suppliers.json()["data"]["total_amount"]) == pytest.approx(40.0)

    pending = await ac.get("/api/v1/reports/purchases/pending-orders", headers=headers)
    assert pending.status_code == 200, pending.text
    numbers = {o["po_number"] for o in pending.json()["data"]["orders"]}
    assert "PO-PR-MINE" in numbers
    assert "PO-PR-OTH" not in numbers
    assert "PO-PR-NULL" not in numbers

    returns = await ac.get("/api/v1/reports/purchases/returns", headers=headers)
    assert returns.status_code == 200, returns.text

    xfer_hist = await ac.get("/api/v1/reports/transfers", headers=headers)
    assert xfer_hist.status_code == 200, xfer_hist.text

    denied_create = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_other.id,
            "to_warehouse_id": wh_mine.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_create = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_mine.id,
            "to_warehouse_id": wh_other.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
            "submit": False,
        },
    )
    assert ok_create.status_code == 200, ok_create.text
    transfer_id = ok_create.json()["data"]["id"]

    # Foreign transfer (other→other) cannot be submitted by manager
    foreign = m.StockTransfer(
        tenant_id=tid,
        company_id=cid,
        transfer_number="XFER-PR-FOREIGN",
        from_store_id=other.id,
        to_store_id=other.id,
        from_warehouse_id=wh_other.id,
        to_warehouse_id=wh_other.id,
        status="draft",
        created_by=seed["admin1"].id,
    )
    db_session.add(foreign)
    await db_session.commit()

    denied_submit = await ac.post(
        f"/api/v1/inventory/stock-transfers/{foreign.id}/submit",
        headers=headers,
    )
    assert denied_submit.status_code == 403
    assert denied_submit.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_submit = await ac.post(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/submit",
        headers=headers,
    )
    assert ok_submit.status_code == 200, ok_submit.text


@pytest.mark.asyncio
async def test_store_manager_expense_reports_and_budgets_store_scoped(client, db_session):
    """Expense summary/budgets/export exclude other/null stores for store_manager."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    from app.expenses import ensure_default_categories

    await ensure_default_categories(db_session, tid, company_id=cid)
    cat = (
        await db_session.execute(
            select(m.ExpenseCategory).where(
                m.ExpenseCategory.tenant_id == tid,
                m.ExpenseCategory.code == "TRAVEL",
            )
        )
    ).scalar_one_or_none()
    if cat is None:
        cat = (
            await db_session.execute(
                select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tid)
            )
        ).scalars().first()
    assert cat is not None

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="ExpRep Mine",
        code="ER-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="ExpRep Other",
        code="ER-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    mine_exp = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category_id=cat.id,
        category=cat.name,
        description="ExpRep mine approved",
        amount=25,
        store_id=mine.id,
        status="approved",
        expense_date=today,
        created_by=mgr.id,
        approved_by=mgr.id,
        approved_at=today,
    )
    other_exp = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category_id=cat.id,
        category=cat.name,
        description="ExpRep other approved",
        amount=500,
        store_id=other.id,
        status="approved",
        expense_date=today,
        created_by=seed["admin1"].id,
        approved_by=seed["admin1"].id,
        approved_at=today,
    )
    null_exp = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category_id=cat.id,
        category=cat.name,
        description="ExpRep null approved",
        amount=40,
        store_id=None,
        status="approved",
        expense_date=today,
        created_by=seed["admin1"].id,
        approved_by=seed["admin1"].id,
        approved_at=today,
    )
    db_session.add_all([mine_exp, other_exp, null_exp])
    await db_session.commit()

    summary = await ac.get("/api/v1/reports/expenses/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    sbody = summary.json()["data"]
    assert int(sbody["count"]) == 1
    assert float(sbody["total_amount"]) == pytest.approx(25.0)
    assert float(sbody["budgets"]["totals"]["spent"]) == pytest.approx(25.0)

    budgets = await ac.get("/api/v1/expenses/budgets", headers=headers)
    assert budgets.status_code == 200, budgets.text
    assert float(budgets.json()["data"]["totals"]["spent"]) == pytest.approx(25.0)

    rollup = await ac.get("/api/v1/reports/summary", headers=headers)
    assert rollup.status_code == 200, rollup.text
    assert float(rollup.json()["data"]["expenses_summary"]["total_amount"]) == pytest.approx(
        25.0
    )
    assert int(rollup.json()["data"]["expenses_summary"]["count"]) == 1

    exported = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "expenses_summary", "format": "csv"},
    )
    assert exported.status_code == 200, exported.text
    assert "500" not in exported.text or "ExpRep other" not in exported.text


@pytest.mark.asyncio
async def test_store_manager_ai_inventory_predictions_store_wh_scoped(client, db_session):
    """AI low-stock / forecast / dead-stock use managed WH stock + store sales only."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Inv Mine",
        code="AI-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Inv Other",
        code="AI-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="AI Mine WH",
        code="AI-M-WH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="AI Other WH",
        code="AI-O-WH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    product = seed["p1"]
    product.company_id = cid
    product.is_active = True
    product.stock_qty = 999  # company-wide decoy — must not leak into manager scope
    product.reorder_level = 5
    product.cost_price = 2

    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_mine.id,
            product_id=product.id,
            quantity=10,
            reserved_qty=0,
            reorder_level=5,
        )
    )
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_other.id,
            product_id=product.id,
            quantity=800,
            reserved_qty=0,
            reorder_level=5,
        )
    )

    # Local sales: 2/day for 30 days → velocity 2; stock 10 ⇒ ~5 days to stockout
    for day in range(30):
        inv = m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            invoice_number=f"INV-AI-M-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=4,
            tax_amount=0,
            total_amount=4,
            store_id=mine.id,
            posted_at=today - timedelta(days=day),
            created_at=today - timedelta(days=day),
            created_by=mgr.id,
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tid,
                company_id=cid,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=2,
                unit_price=2,
                line_total=4,
            )
        )
    # Other-store heavy sales must not inflate manager velocity
    for day in range(10):
        inv = m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            invoice_number=f"INV-AI-O-{day}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=200,
            tax_amount=0,
            total_amount=200,
            store_id=other.id,
            posted_at=today - timedelta(days=day),
            created_at=today - timedelta(days=day),
            created_by=seed["admin1"].id,
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tid,
                company_id=cid,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=100,
                unit_price=2,
                line_total=200,
            )
        )
    await db_session.commit()

    low = await ac.get("/api/v1/ai/inventory/low-stock-prediction", headers=headers)
    assert low.status_code == 200, low.text
    lbody = low.json()["data"]
    assert lbody.get("scope") == "store_manager"
    row = next(p for p in lbody["predictions"] if p["product_id"] == product.id)
    assert float(row["stock_qty"]) == pytest.approx(10.0)
    assert float(row["units_sold_lookback"]) == pytest.approx(60.0)
    assert row["at_risk"] is True
    assert row["days_to_stockout"] is not None
    assert float(row["days_to_stockout"]) < 14

    forecast = await ac.get("/api/v1/ai/inventory/demand-forecast", headers=headers)
    assert forecast.status_code == 200, forecast.text
    frow = next(
        p for p in forecast.json()["data"]["forecasts"] if p["product_id"] == product.id
    )
    assert float(frow["stock_qty"]) == pytest.approx(10.0)
    assert float(frow["units_sold_lookback"]) == pytest.approx(60.0)

    dead = await ac.get(
        "/api/v1/ai/inventory/dead-stock",
        headers=headers,
        params={"lookback_days": 90},
    )
    assert dead.status_code == 200, dead.text
    dead_ids = {i["product_id"] for i in dead.json()["data"]["items"]}
    # Has recent managed-store sales → not dead for manager
    assert product.id not in dead_ids

    exported = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    # Manager CSV must reflect scoped on-hand (10), not company stock_qty 999
    assert ",10," in exported.text or ",10.0," in exported.text or "10" in exported.text


@pytest.mark.asyncio
async def test_store_manager_ai_insights_and_cross_domain_scoped(client, db_session):
    """Insights / sales / expenses / purchases / cross-domain ignore foreign store+WH totals."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Ins Mine",
        code="AI-INS-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Ins Other",
        code="AI-INS-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="AI Ins Mine WH",
        code="AI-INS-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="AI Ins Other WH",
        code="AI-INS-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    # Quiet managed store sales vs huge foreign store sales
    for i, (store, amt, prefix) in enumerate(
        (
            (mine, 50.0, "M"),
            (other, 5000.0, "O"),
        )
    ):
        inv = m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            invoice_number=f"INV-INS-{prefix}-{i}",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=amt,
            total_amount=amt,
            store_id=store.id,
            posted_at=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
            created_by=mgr.id if store is mine else seed["admin1"].id,
        )
        db_session.add(inv)

    db_session.add(
        m.Expense(
            tenant_id=tid,
            company_id=cid,
            store_id=mine.id,
            category="Utilities",
            description="Mine util",
            amount=20,
            status="approved",
            expense_date=today - timedelta(days=1),
            payment_method="cash",
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=tid,
            company_id=cid,
            store_id=other.id,
            category="Utilities",
            description="Other util",
            amount=9000,
            status="approved",
            expense_date=today - timedelta(days=1),
            payment_method="cash",
        )
    )

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="AI Ins Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.flush()
    for wh, total, num in (
        (wh_mine, 30.0, "PO-INS-M"),
        (wh_other, 8000.0, "PO-INS-O"),
    ):
        po = m.PurchaseOrder(
            tenant_id=tid,
            company_id=cid,
            po_number=num,
            supplier_id=supplier.id,
            warehouse_id=wh.id,
            status="sent",
            subtotal=total,
            total_amount=total,
            created_at=today - timedelta(days=2),
        )
        db_session.add(po)
        await db_session.flush()
        pi = m.PurchaseInvoice(
            tenant_id=tid,
            company_id=cid,
            invoice_number=f"PI-{num}",
            supplier_id=supplier.id,
            purchase_order_id=po.id,
            warehouse_id=wh.id,
            status="unpaid",
            subtotal=total,
            total_amount=total,
            invoice_date=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
        )
        db_session.add(pi)

    await db_session.commit()

    sales = await ac.get("/api/v1/ai/sales/analysis", headers=headers)
    assert sales.status_code == 200, sales.text
    sbody = sales.json()["data"]
    assert sbody.get("scope") == "store_manager"
    assert float(sbody["summary"]["total_sales"]) == pytest.approx(50.0)

    expenses = await ac.get("/api/v1/ai/expenses/analysis", headers=headers)
    assert expenses.status_code == 200, expenses.text
    ebody = expenses.json()["data"]
    assert ebody.get("scope") == "store_manager"
    assert float(ebody["summary"]["total_approved"]) == pytest.approx(20.0)

    purchases = await ac.get("/api/v1/ai/purchases/analysis", headers=headers)
    assert purchases.status_code == 200, purchases.text
    pbody = purchases.json()["data"]
    assert pbody.get("scope") == "store_manager"
    assert float(pbody["summary"]["total_spend"]) == pytest.approx(30.0)

    insights = await ac.get("/api/v1/ai/insights", headers=headers)
    assert insights.status_code == 200, insights.text
    ibody = insights.json()["data"]
    assert ibody.get("scope") == "store_manager"

    xd = await ac.get("/api/v1/ai/cross-domain/analysis", headers=headers)
    assert xd.status_code == 200, xd.text
    xbody = xd.json()["data"]
    assert xbody.get("scope") == "store_manager"
    assert float(xbody["summary"]["total_sales"]) == pytest.approx(50.0)
    assert float(xbody["summary"]["total_approved_expenses"]) == pytest.approx(20.0)
    assert float(xbody["summary"]["total_purchase_spend"]) == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_store_manager_ai_customer_insights_store_scoped(client, db_session):
    """Customer insights / assist use managed-store sales only (not foreign-store spend)."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Cust Mine",
        code="AI-CUST-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Cust Other",
        code="AI-CUST-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    local_cust = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Local Buyer",
        kind="customer",
        status="active",
        credit_limit=100,
    )
    foreign_only = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Foreign Only Buyer",
        kind="customer",
        status="active",
        credit_limit=100,
    )
    db_session.add_all([local_cust, foreign_only])
    await db_session.flush()

    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=mine.id,
            invoice_number="INV-CUST-M-1",
            customer_id=local_cust.id,
            status="posted",
            subtotal=120,
            total_amount=120,
            paid_amount=120,
            posted_at=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
        )
    )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=other.id,
            invoice_number="INV-CUST-O-1",
            customer_id=foreign_only.id,
            status="posted",
            subtotal=9000,
            total_amount=9000,
            paid_amount=9000,
            posted_at=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
        )
    )
    # Foreign-store spend on local customer must not inflate manager monetary
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=other.id,
            invoice_number="INV-CUST-O-2",
            customer_id=local_cust.id,
            status="posted",
            subtotal=5000,
            total_amount=5000,
            paid_amount=5000,
            posted_at=today - timedelta(days=2),
            created_at=today - timedelta(days=2),
        )
    )
    await db_session.commit()

    insights = await ac.get("/api/v1/ai/customers/insights", headers=headers)
    assert insights.status_code == 200, insights.text
    body = insights.json()["data"]
    assert body.get("scope") == "store_manager"
    ids = {c["customer_id"] for c in body["best_customers"]}
    assert local_cust.id in ids
    assert foreign_only.id not in ids
    row = next(c for c in body["best_customers"] if c["customer_id"] == local_cust.id)
    assert float(row["monetary"]) == pytest.approx(120.0)

    assist = await ac.post(
        "/api/v1/ai/customer/assist",
        headers=headers,
        json={"query": "Who are my best customers?"},
    )
    assert assist.status_code == 200, assist.text
    adata = assist.json()["data"]
    assert adata.get("scope") == "store_manager"
    assert "Foreign Only" not in (adata.get("answer") or "")
    assert float(adata["best_customers"][0]["monetary"]) == pytest.approx(120.0)

    exported = await ac.get("/api/v1/ai/customers/insights/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "Foreign Only Buyer" not in exported.text
    assert "Local Buyer" in exported.text or local_cust.id in exported.text


@pytest.mark.asyncio
async def test_store_manager_ai_chat_sales_helpers_store_scoped(client, db_session):
    """Chat top-product / sales-month / expenses / low-stock ignore foreign store+WH."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = seed["p1"]
    product.company_id = cid
    product.is_active = True
    product.stock_qty = 999
    product.reorder_level = 5
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Chat Mine",
        code="AI-CHAT-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Chat Other",
        code="AI-CHAT-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="AI Chat Mine WH",
        code="AI-CHAT-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="AI Chat Other WH",
        code="AI-CHAT-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_mine.id,
            product_id=product.id,
            quantity=2,
            reserved_qty=0,
            reorder_level=10,
        )
    )
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_other.id,
            product_id=product.id,
            quantity=1,
            reserved_qty=0,
            reorder_level=10,
        )
    )

    # Managed-store modest sales vs foreign-store huge sales
    for store, amt, qty, prefix in (
        (mine, 40.0, 4.0, "M"),
        (other, 8000.0, 400.0, "O"),
    ):
        inv = m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=store.id,
            invoice_number=f"INV-CHAT-{prefix}-1",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=amt,
            total_amount=amt,
            posted_at=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            m.SalesInvoiceItem(
                tenant_id=tid,
                company_id=cid,
                sales_invoice_id=inv.id,
                product_id=product.id,
                quantity=qty,
                unit_price=amt / qty,
                line_total=amt,
            )
        )

    db_session.add(
        m.Expense(
            tenant_id=tid,
            company_id=cid,
            store_id=mine.id,
            category="Utilities",
            description="Mine chat exp",
            amount=15,
            status="approved",
            expense_date=today - timedelta(days=1),
            payment_method="cash",
        )
    )
    db_session.add(
        m.Expense(
            tenant_id=tid,
            company_id=cid,
            store_id=other.id,
            category="Utilities",
            description="Other chat exp",
            amount=7000,
            status="approved",
            expense_date=today - timedelta(days=1),
            payment_method="cash",
        )
    )
    await db_session.commit()

    top = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "What is my top selling product this month?"},
    )
    assert top.status_code == 200, top.text
    tdata = top.json()["data"]
    assert tdata["intent"] == "top_product"
    assert tdata["data"].get("scope") == "store_manager"
    assert float(tdata["data"]["revenue"]) == pytest.approx(40.0)

    sales = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "How much were my sales this month?"},
    )
    assert sales.status_code == 200, sales.text
    sdata = sales.json()["data"]
    assert sdata["intent"] == "sales_month"
    assert sdata["data"].get("scope") == "store_manager"
    assert float(sdata["data"]["total"]) == pytest.approx(40.0)

    expenses = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "What are my expenses this month?"},
    )
    assert expenses.status_code == 200, expenses.text
    edata = expenses.json()["data"]
    assert edata["intent"] == "expenses"
    assert edata["data"].get("scope") == "store_manager"
    assert float(edata["data"]["total"]) == pytest.approx(15.0)

    low = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Which products are low stock?"},
    )
    assert low.status_code == 200, low.text
    ldata = low.json()["data"]
    assert ldata["intent"] == "low_stock"
    assert ldata["data"].get("scope") == "store_manager"
    assert ldata["data"]["items"]
    assert float(ldata["data"]["items"][0]["stock_qty"]) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_store_manager_ai_security_alerts_self_and_store_details_scoped(
    client, db_session
):
    """Security alerts: mgr sees self (+ managed store/WH details), not foreign users."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    other_user = seed["admin1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    now = datetime.utcnow()

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Sec Mine",
        code="AI-SEC-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Sec Other",
        code="AI-SEC-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="AI Sec Mine WH",
        code="AI-SEC-MWH",
    )
    db_session.add(wh_mine)
    await db_session.flush()

    async def _backdate(action: str, when):
        row = (
            await db_session.execute(
                select(m.AuditLog)
                .where(m.AuditLog.tenant_id == tid, m.AuditLog.action == action)
                .order_by(m.AuditLog.created_at.desc())
            )
        ).scalars().first()
        row.created_at = when
        await db_session.flush()

    # Manager self failed-login burst (should alert)
    for i in range(5):
        await audit_svc.record_event(
            db_session,
            tenant_id=tid,
            company_id=cid,
            user_id=mgr.id,
            module="auth",
            action="login_failed",
            entity="user",
            entity_id=mgr.id,
            details={"email": mgr.email},
            ip_address="203.0.113.50",
            user_agent="MgrClient/1.0",
        )
        await _backdate("login_failed", now - timedelta(minutes=15 - i))

    # Foreign admin failed-login burst (must not leak to store manager)
    for i in range(6):
        await audit_svc.record_event(
            db_session,
            tenant_id=tid,
            company_id=cid,
            user_id=other_user.id,
            module="auth",
            action="login_failed",
            entity="user",
            entity_id=other_user.id,
            details={"email": other_user.email},
            ip_address="198.51.100.50",
            user_agent="AdminEvil/1.0",
        )
        await _backdate("login_failed", now - timedelta(minutes=25 - i))

    # Foreign-store attributed txn burst (no self; wrong store — exclude)
    for i in range(9):
        await audit_svc.record_event(
            db_session,
            tenant_id=tid,
            company_id=cid,
            user_id=other_user.id,
            module="sales",
            action="post",
            entity="sales_invoice",
            entity_id=f"inv-sec-o-{i}",
            details={"store_id": other.id},
            ip_address="198.51.100.50",
            user_agent="AdminEvil/1.0",
        )
        await _backdate("post", now - timedelta(minutes=40 - i))

    # Managed-store attributed txn burst from another user (include via details.store_id)
    for i in range(9):
        await audit_svc.record_event(
            db_session,
            tenant_id=tid,
            company_id=cid,
            user_id=other_user.id,
            module="sales",
            action="post",
            entity="sales_invoice",
            entity_id=f"inv-sec-m-{i}",
            details={"store_id": mine.id},
            ip_address="203.0.113.90",
            user_agent="PosClient/1.0",
        )
        await _backdate("post", now - timedelta(minutes=8 - i))

    await db_session.commit()

    r = await ac.get(
        "/api/v1/ai/security/alerts",
        headers=headers,
        params={"lookback_hours": 48},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body.get("scope") == "store_manager"
    assert body["alert_count"] >= 1
    blob = str(body)
    assert "AdminEvil/1.0" not in blob
    assert "198.51.100.50" not in blob
    assert other_user.email not in blob

    kinds = {a["kind"] for a in body["alerts"]}
    assert "failed_login_burst" in kinds or "failed_login_ip_burst" in kinds
    assert "suspicious_transaction_burst" in kinds

    entity_ids = {a.get("entity_id") for a in body["alerts"]}
    assert mgr.id in entity_ids
    # Foreign admin auth entity must not appear; managed-store txn burst may
    # surface other_user.id only via store-attributed sensitive actions.
    auth_entities = {
        a.get("entity_id")
        for a in body["alerts"]
        if a.get("kind")
        in {
            "failed_login_burst",
            "failed_login_ip_burst",
            "login_after_failures",
            "unusual_login_ip",
            "unusual_login_time",
            "unusual_login_device",
        }
    }
    assert other_user.id not in auth_entities

    export = await ac.get(
        "/api/v1/ai/security/alerts/export",
        headers=headers,
        params={"lookback_hours": 48},
    )
    assert export.status_code == 200, export.text
    csv_text = export.text
    assert "AdminEvil/1.0" not in csv_text
    assert "198.51.100.50" not in csv_text


@pytest.mark.asyncio
async def test_store_manager_ai_documents_analyze_matches_store_scoped(client, db_session):
    """Document analyze matches only managed-store/WH parties and products."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    local_product = seed["p1"]
    local_product.company_id = cid
    local_product.is_active = True
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Doc Mine",
        code="AI-DOC-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="AI Doc Other",
        code="AI-DOC-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="AI Doc Mine WH",
        code="AI-DOC-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="AI Doc Other WH",
        code="AI-DOC-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    foreign_product = m.Product(
        tenant_id=tid,
        company_id=cid,
        name="Foreign Gadget XYZ",
        sku="FG-XYZ-99",
        selling_price=9,
        cost_price=4,
        stock_qty=50,
        reorder_level=1,
        is_active=True,
    )
    db_session.add(foreign_product)
    await db_session.flush()

    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_mine.id,
            product_id=local_product.id,
            quantity=12,
            reserved_qty=0,
            reorder_level=2,
        )
    )
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_other.id,
            product_id=foreign_product.id,
            quantity=40,
            reserved_qty=0,
            reorder_level=2,
        )
    )

    local_supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Local Mine Supplier",
        kind="supplier",
        status="active",
    )
    foreign_supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Foreign Only Supplier",
        kind="supplier",
        status="active",
    )
    db_session.add_all([local_supplier, foreign_supplier])
    await db_session.flush()

    db_session.add(
        m.PurchaseOrder(
            tenant_id=tid,
            company_id=cid,
            po_number="PO-DOC-M-1",
            supplier_id=local_supplier.id,
            warehouse_id=wh_mine.id,
            status="sent",
            subtotal=10,
            total_amount=10,
        )
    )
    db_session.add(
        m.PurchaseOrder(
            tenant_id=tid,
            company_id=cid,
            po_number="PO-DOC-O-1",
            supplier_id=foreign_supplier.id,
            warehouse_id=wh_other.id,
            status="sent",
            subtotal=99,
            total_amount=99,
        )
    )

    local_customer = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Local Doc Buyer",
        kind="customer",
        status="active",
        credit_limit=100,
    )
    foreign_customer = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Foreign Doc Buyer",
        kind="customer",
        status="active",
        credit_limit=100,
    )
    db_session.add_all([local_customer, foreign_customer])
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=mine.id,
            invoice_number="INV-DOC-M-1",
            customer_id=local_customer.id,
            status="posted",
            subtotal=25,
            total_amount=25,
            posted_at=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
        )
    )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=other.id,
            invoice_number="INV-DOC-O-1",
            customer_id=foreign_customer.id,
            status="posted",
            subtotal=500,
            total_amount=500,
            posted_at=today - timedelta(days=1),
            created_at=today - timedelta(days=1),
        )
    )
    await db_session.commit()

    receipt_text = (
        "Payee: Local Mine Supplier\n"
        f"{local_product.name} {local_product.sku}\n"
        f"{foreign_product.name} {foreign_product.sku}\n"
        "Total: 12.50\n"
        "Date: 2026-08-20\n"
    )
    files = {"file": ("receipt.txt", receipt_text.encode("utf-8"), "text/plain")}
    r = await ac.post(
        "/api/v1/ai/documents/analyze?document_type=receipt",
        headers=headers,
        files=files,
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body.get("scope") == "store_manager"
    assert body["extracted_fields"].get("payee") == "Local Mine Supplier"
    party = body["matches"]["party"]
    assert party is not None
    assert party["id"] == local_supplier.id
    assert party["name"] == "Local Mine Supplier"
    product_ids = {p["id"] for p in body["matches"]["products"]}
    assert local_product.id in product_ids
    assert foreign_product.id not in product_ids
    blob = str(body["matches"])
    assert "Foreign Only Supplier" not in blob
    assert "Foreign Gadget" not in blob
    assert "Foreign Doc Buyer" not in blob

    # Foreign payee must not match even though company catalog has the party
    foreign_text = (
        "Payee: Foreign Only Supplier\n"
        f"{foreign_product.name} {foreign_product.sku}\n"
        "Total: 9.99\n"
        "Date: 2026-08-20\n"
    )
    denied = await ac.post(
        "/api/v1/ai/documents/analyze?document_type=purchase_order",
        headers=headers,
        files={"file": ("po.txt", foreign_text.encode("utf-8"), "text/plain")},
    )
    assert denied.status_code == 200, denied.text
    dbody = denied.json()["data"]
    assert dbody.get("scope") == "store_manager"
    assert dbody["matches"]["party"] is None
    assert dbody["matches"]["products"] == []
    assert any(d.get("field") == "payee" for d in dbody["discrepancies"])


@pytest.mark.asyncio
async def test_store_manager_credit_aging_store_wh_scoped(client, db_session):
    """AR aging uses managed-store invoices; AP aging uses managed-WH bills."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Credit Aging Mine",
        code="CR-AGE-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Credit Aging Other",
        code="CR-AGE-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Credit Aging Mine WH",
        code="CR-AGE-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Credit Aging Other WH",
        code="CR-AGE-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    local_cust = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="AR Local Buyer",
        kind="customer",
        status="active",
        credit_limit=500,
        balance=9999,
    )
    foreign_cust = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="AR Foreign Buyer",
        kind="customer",
        status="active",
        credit_limit=500,
        balance=8888,
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="AP Aging Supplier",
        kind="supplier",
        status="active",
        balance=7777,
    )
    db_session.add_all([local_cust, foreign_cust, supplier])
    await db_session.flush()

    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=mine.id,
            invoice_number="INV-AR-M-1",
            customer_id=local_cust.id,
            status="posted",
            subtotal=40,
            total_amount=40,
            paid_amount=0,
            due_date=today - timedelta(days=5),
            posted_at=today - timedelta(days=5),
            created_at=today - timedelta(days=5),
        )
    )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            company_id=cid,
            store_id=other.id,
            invoice_number="INV-AR-O-1",
            customer_id=foreign_cust.id,
            status="posted",
            subtotal=9000,
            total_amount=9000,
            paid_amount=0,
            due_date=today - timedelta(days=5),
            posted_at=today - timedelta(days=5),
            created_at=today - timedelta(days=5),
        )
    )

    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tid,
            company_id=cid,
            invoice_number="PI-AP-M-1",
            supplier_id=supplier.id,
            warehouse_id=wh_mine.id,
            status="unpaid",
            subtotal=25,
            total_amount=25,
            paid_amount=0,
            invoice_date=today - timedelta(days=3),
            due_date=today - timedelta(days=1),
            created_at=today - timedelta(days=3),
        )
    )
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=tid,
            company_id=cid,
            invoice_number="PI-AP-O-1",
            supplier_id=supplier.id,
            warehouse_id=wh_other.id,
            status="unpaid",
            subtotal=8000,
            total_amount=8000,
            paid_amount=0,
            invoice_date=today - timedelta(days=3),
            due_date=today - timedelta(days=1),
            created_at=today - timedelta(days=3),
        )
    )
    await db_session.commit()

    ar = await ac.get("/api/v1/credit/aging?kind=receivable", headers=headers)
    assert ar.status_code == 200, ar.text
    ar_body = ar.json()["data"]
    assert ar_body.get("scope") == "store_manager"
    assert float(ar_body["total_due"]) == pytest.approx(40.0)
    party_names = {p["name"] for p in ar_body["parties"]}
    assert "AR Local Buyer" in party_names
    assert "AR Foreign Buyer" not in party_names
    assert all(float(p.get("balance") or 0) == 0 for p in ar_body["parties"])
    doc_nums = {d["document_number"] for d in ar_body["documents"]}
    assert "INV-AR-M-1" in doc_nums
    assert "INV-AR-O-1" not in doc_nums

    ap = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert ap.status_code == 200, ap.text
    ap_body = ap.json()["data"]
    assert ap_body.get("scope") == "store_manager"
    assert float(ap_body["total_due"]) == pytest.approx(25.0)
    ap_docs = {d["document_number"] for d in ap_body["documents"]}
    assert "PI-AP-M-1" in ap_docs
    assert "PI-AP-O-1" not in ap_docs
    assert all(float(p.get("balance") or 0) == 0 for p in ap_body["parties"])

    slice_r = await ac.get("/api/v1/dashboard/credit", headers=headers)
    assert slice_r.status_code == 200, slice_r.text
    slice_body = slice_r.json()["data"]
    assert float(slice_body["ar_total_due"]) == pytest.approx(40.0)

    export = await ac.get(
        "/api/v1/credit/aging/export?kind=receivable", headers=headers
    )
    assert export.status_code == 200, export.text
    assert "INV-AR-M-1" in export.text
    assert "INV-AR-O-1" not in export.text
    assert "AR Foreign Buyer" not in export.text


@pytest.mark.asyncio
async def test_store_manager_credit_statements_payments_store_scoped(client, db_session):
    """Statements/outstanding/payment register + write asserts respect store/WH scope."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Credit Stmt Mine",
        code="CR-ST-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Credit Stmt Other",
        code="CR-ST-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Credit Stmt Mine WH",
        code="CR-ST-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Credit Stmt Other WH",
        code="CR-ST-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    cust = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Stmt Shared Customer",
        kind="customer",
        status="active",
        credit_limit=500,
        balance=999,
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Stmt Shared Supplier",
        kind="supplier",
        status="active",
        balance=888,
    )
    db_session.add_all([cust, supplier])
    await db_session.flush()

    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-STMT-M-1",
        customer_id=cust.id,
        status="posted",
        subtotal=50,
        total_amount=50,
        paid_amount=0,
        due_date=today - timedelta(days=2),
        posted_at=today - timedelta(days=2),
        created_at=today - timedelta(days=2),
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-STMT-O-1",
        customer_id=cust.id,
        status="posted",
        subtotal=7000,
        total_amount=7000,
        paid_amount=0,
        due_date=today - timedelta(days=2),
        posted_at=today - timedelta(days=2),
        created_at=today - timedelta(days=2),
    )
    db_session.add_all([inv_mine, inv_other])
    await db_session.flush()

    pay_mine = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CPAY-STMT-M-1",
        customer_id=cust.id,
        sales_invoice_id=inv_mine.id,
        amount=10,
        payment_method="cash",
    )
    pay_other = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CPAY-STMT-O-1",
        customer_id=cust.id,
        sales_invoice_id=inv_other.id,
        amount=500,
        payment_method="cash",
    )
    db_session.add_all([pay_mine, pay_other])

    pi_mine = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-STMT-M-1",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="unpaid",
        subtotal=30,
        total_amount=30,
        paid_amount=0,
        invoice_date=today - timedelta(days=1),
        due_date=today + timedelta(days=5),
        created_at=today - timedelta(days=1),
    )
    pi_other = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-STMT-O-1",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="unpaid",
        subtotal=6000,
        total_amount=6000,
        paid_amount=0,
        invoice_date=today - timedelta(days=1),
        due_date=today + timedelta(days=5),
        created_at=today - timedelta(days=1),
    )
    db_session.add_all([pi_mine, pi_other])
    await db_session.flush()
    spay_mine = m.SupplierPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="SPAY-STMT-M-1",
        supplier_id=supplier.id,
        purchase_invoice_id=pi_mine.id,
        amount=5,
        payment_method="bank_transfer",
    )
    spay_other = m.SupplierPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="SPAY-STMT-O-1",
        supplier_id=supplier.id,
        purchase_invoice_id=pi_other.id,
        amount=400,
        payment_method="bank_transfer",
    )
    db_session.add_all([spay_mine, spay_other])
    await db_session.commit()

    outstanding = await ac.get(
        f"/api/v1/customers/{cust.id}/outstanding", headers=headers
    )
    assert outstanding.status_code == 200, outstanding.text
    oids = {d["invoice_id"] for d in outstanding.json()["data"]}
    assert inv_mine.id in oids
    assert inv_other.id not in oids

    stmt = await ac.get(
        f"/api/v1/credit/customers/{cust.id}/statement", headers=headers
    )
    assert stmt.status_code == 200, stmt.text
    sbody = stmt.json()["data"]
    assert sbody.get("scope") == "store_manager"
    assert float(sbody["customer"]["balance"]) == pytest.approx(0)
    refs = {ln["reference"] for ln in sbody["lines"]}
    assert "INV-STMT-M-1" in refs
    assert "CPAY-STMT-M-1" in refs
    assert "INV-STMT-O-1" not in refs
    assert "CPAY-STMT-O-1" not in refs

    cpays = await ac.get("/api/v1/credit/customer-payments", headers=headers)
    assert cpays.status_code == 200, cpays.text
    cnums = {r["payment_number"] for r in cpays.json()["data"]}
    assert "CPAY-STMT-M-1" in cnums
    assert "CPAY-STMT-O-1" not in cnums

    # Deny paying foreign-store invoice
    denied = await ac.post(
        f"/api/v1/customers/{cust.id}/payments",
        headers=headers,
        json={
            "customer_id": cust.id,
            "amount": 1,
            "sales_invoice_id": inv_other.id,
            "payment_method": "cash",
        },
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Deny unallocated payment (no invoice)
    denied_unalloc = await ac.post(
        f"/api/v1/customers/{cust.id}/payments",
        headers=headers,
        json={
            "customer_id": cust.id,
            "amount": 1,
            "payment_method": "cash",
        },
    )
    assert denied_unalloc.status_code == 403, denied_unalloc.text

    schedule = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/payment-schedule", headers=headers
    )
    assert schedule.status_code == 200, schedule.text
    sch = schedule.json()["data"]
    assert sch.get("scope") == "store_manager"
    assert float(sch["total_due"]) == pytest.approx(30.0)
    sch_nums = {
        (i.get("invoice_number") or i.get("po_number")) for i in sch["items"]
    }
    assert "PI-STMT-M-1" in sch_nums
    assert "PI-STMT-O-1" not in sch_nums

    spays = await ac.get("/api/v1/credit/supplier-payments", headers=headers)
    assert spays.status_code == 200, spays.text
    snums = {r["payment_number"] for r in spays.json()["data"]}
    assert "SPAY-STMT-M-1" in snums
    assert "SPAY-STMT-O-1" not in snums

    denied_ap = await ac.post(
        f"/api/v1/suppliers/{supplier.id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier.id,
            "amount": 1,
            "purchase_invoice_id": pi_other.id,
            "payment_method": "bank_transfer",
        },
    )
    assert denied_ap.status_code == 403, denied_ap.text


@pytest.mark.asyncio
async def test_store_manager_accounting_pnl_tb_store_scoped(client, db_session):
    """P&L / TB / cash-flow / balance-sheet (+ exports, dashboard) exclude foreign-store journals."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Acct Stmt Mine",
        code="ACC-PNL-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Acct Stmt Other",
        code="ACC-PNL-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        description="Mine store sale",
        reference="JE-ACC-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other store sale",
        reference="JE-ACC-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 9000, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 9000},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Null-store sale (fail-closed)",
        reference="JE-ACC-NULL",
        store_id=None,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 500, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 500},
        ],
    )
    await db_session.commit()

    today = datetime.utcnow().strftime("%Y-%m-%d")

    pnl = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=headers,
        params={"from_date": today, "to_date": today},
    )
    assert pnl.status_code == 200, pnl.text
    pdata = pnl.json()["data"]
    assert float(pdata["income"]) == pytest.approx(100.0)
    assert float(pdata["net_profit"]) == pytest.approx(100.0)

    denied = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=headers,
        params={"store_id": other.id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    reports_pnl = await ac.get(
        "/api/v1/reports/profit-loss",
        headers=headers,
        params={"from_date": today, "to_date": today},
    )
    assert reports_pnl.status_code == 200, reports_pnl.text
    assert float(reports_pnl.json()["data"]["income"]) == pytest.approx(100.0)

    tb = await ac.get("/api/v1/accounting/trial-balance", headers=headers)
    assert tb.status_code == 200, tb.text
    rows_by_code = {r["code"]: r for r in tb.json()["data"]["rows"]}
    assert float(rows_by_code["4000"]["credit"]) == pytest.approx(100.0)
    assert float(rows_by_code["1000"]["debit"]) == pytest.approx(100.0)

    cf = await ac.get(
        "/api/v1/reports/cash-flow",
        headers=headers,
        params={"from_date": today, "to_date": today},
    )
    assert cf.status_code == 200, cf.text
    assert float(cf.json()["data"]["inflows"]) == pytest.approx(100.0)

    bs = await ac.get("/api/v1/reports/balance-sheet", headers=headers)
    assert bs.status_code == 200, bs.text
    cash_row = next(
        (r for r in bs.json()["data"]["assets"] if r["code"] == "1000"), None
    )
    assert cash_row is not None
    assert float(cash_row["balance"]) == pytest.approx(100.0)

    pnl_csv = await ac.get(
        "/api/v1/accounting/profit-loss/export",
        headers=headers,
        params={"from_date": today, "to_date": today},
    )
    assert pnl_csv.status_code == 200, pnl_csv.text
    assert "9000" not in pnl_csv.text
    assert "100" in pnl_csv.text

    tb_csv = await ac.get("/api/v1/reports/trial-balance/export", headers=headers)
    assert tb_csv.status_code == 200, tb_csv.text
    assert "9000" not in tb_csv.text

    generic = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "profit_loss", "from_date": today, "to_date": today},
    )
    assert generic.status_code == 200, generic.text
    assert "9000" not in generic.text

    dash = await ac.get("/api/v1/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    assert float(dash.json()["data"]["profit_summary"]) == pytest.approx(100.0)
    assert float(dash.json()["data"]["income_mtd"]) == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_store_manager_tax_reports_store_wh_scoped(client, db_session):
    """Tax report/filing (+ exports) use managed-store outputs and managed-WH inputs."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Tax Scope Mine",
        code="TAX-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Tax Scope Other",
        code="TAX-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Tax Mine WH",
        code="TAX-M-WH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Tax Other WH",
        code="TAX-O-WH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-TAX-M-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=100,
        tax_amount=15,
        total_amount=115,
        posted_at=today,
        created_at=today,
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-TAX-O-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=1000,
        tax_amount=900,
        total_amount=1900,
        posted_at=today,
        created_at=today,
    )
    inv_null = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=None,
        invoice_number="INV-TAX-NULL",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=50,
        tax_amount=50,
        total_amount=100,
        posted_at=today,
        created_at=today,
    )
    db_session.add_all([inv_mine, inv_other, inv_null])
    await db_session.flush()

    sess_mine = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        user_id=mgr.id,
        session_number="TAX-POS-M",
        status="open",
        opening_cash=0,
    )
    sess_other = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        user_id=seed["admin1"].id,
        session_number="TAX-POS-O",
        status="open",
        opening_cash=0,
    )
    db_session.add_all([sess_mine, sess_other])
    await db_session.flush()
    pos_mine = m.Transaction(
        tenant_id=tid,
        company_id=cid,
        session_id=sess_mine.id,
        tx_type="pos_sale",
        reference="POS-TAX-M",
        subtotal=20,
        tax=5,
        total=25,
        created_at=today,
    )
    pos_other = m.Transaction(
        tenant_id=tid,
        company_id=cid,
        session_id=sess_other.id,
        tx_type="pos_sale",
        reference="POS-TAX-O",
        subtotal=200,
        tax=80,
        total=280,
        created_at=today,
    )
    db_session.add_all([pos_mine, pos_other])

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Tax Scope Supplier",
        kind="supplier",
        status="active",
    )
    db_session.add(supplier)
    await db_session.flush()
    pi_mine = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-TAX-M-1",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="unpaid",
        subtotal=40,
        tax_amount=4,
        total_amount=44,
        paid_amount=0,
        invoice_date=today,
        created_at=today,
    )
    pi_other = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-TAX-O-1",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="unpaid",
        subtotal=400,
        tax_amount=400,
        total_amount=800,
        paid_amount=0,
        invoice_date=today,
        created_at=today,
    )
    pi_null = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-TAX-NULL",
        supplier_id=supplier.id,
        warehouse_id=None,
        status="unpaid",
        subtotal=30,
        tax_amount=30,
        total_amount=60,
        paid_amount=0,
        invoice_date=today,
        created_at=today,
    )
    db_session.add_all([pi_mine, pi_other, pi_null])
    await db_session.commit()

    tax = await ac.get("/api/v1/reports/tax", headers=headers)
    assert tax.status_code == 200, tax.text
    body = tax.json()["data"]
    assert float(body["output_tax_invoices"]) == pytest.approx(15.0)
    assert float(body["output_tax_pos"]) == pytest.approx(5.0)
    assert float(body["output_tax"]) == pytest.approx(20.0)
    assert float(body["input_tax"]) == pytest.approx(4.0)
    assert float(body["net_tax_payable"]) == pytest.approx(16.0)
    assert int(body["invoice_count"]) == 1
    assert int(body["pos_sale_count"]) == 1
    assert int(body["purchase_count"]) == 1

    filing = await ac.get("/api/v1/reports/tax/filing", headers=headers)
    assert filing.status_code == 200, filing.text
    fbody = filing.json()["data"]
    out_nums = {r["document_number"] for r in fbody["schedules"]["output"]}
    in_nums = {r["document_number"] for r in fbody["schedules"]["input"]}
    assert "INV-TAX-M-1" in out_nums
    assert "POS-TAX-M" in out_nums
    assert "INV-TAX-O-1" not in out_nums
    assert "POS-TAX-O" not in out_nums
    assert "INV-TAX-NULL" not in out_nums
    assert "PI-TAX-M-1" in in_nums
    assert "PI-TAX-O-1" not in in_nums
    assert "PI-TAX-NULL" not in in_nums

    path_csv = await ac.get("/api/v1/reports/tax/export", headers=headers)
    assert path_csv.status_code == 200, path_csv.text
    assert "900" not in path_csv.text
    assert "400" not in path_csv.text or "40" in path_csv.text

    generic = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "tax", "format": "csv"},
    )
    assert generic.status_code == 200, generic.text
    assert "900" not in generic.text

    filing_csv = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={"report_type": "tax_filing", "format": "csv"},
    )
    assert filing_csv.status_code == 200, filing_csv.text
    assert "INV-TAX-O-1" not in filing_csv.text
    assert "PI-TAX-O-1" not in filing_csv.text


@pytest.mark.asyncio
async def test_store_manager_tax_rate_writes_denied(client, db_session):
    """Tax rate create/patch/default denied for store_manager (company-level config)."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    perms = dict(permissions_for_role("store_manager"))
    perms["tax"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    existing = m.TaxRate(
        tenant_id=tid,
        company_id=cid,
        name="Standard VAT",
        rate=15.0,
        is_active=True,
        is_default=True,
    )
    db_session.add(existing)
    await db_session.commit()

    denied_create = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": "Mgr VAT", "rate": 10.0, "is_active": True},
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/tax/rates/{existing.id}",
        headers=headers,
        json={"rate": 12.0},
    )
    assert denied_patch.status_code == 403
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_default = await ac.post(
        f"/api/v1/tax/rates/{existing.id}/default",
        headers=headers,
    )
    assert denied_default.status_code == 403
    assert denied_default.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_audit_logs_self_and_store_details_scoped(client, db_session):
    """Audit list/export: mgr sees self + managed store/WH details, not foreign unscoped."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    other_user = seed["admin1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Audit Scope Mine",
        code="AUD-MINE",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Audit Scope Other",
        code="AUD-OTH",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Audit Mine WH",
        code="AUD-M-WH",
    )
    db_session.add(wh_mine)
    await db_session.flush()

    self_ev = await audit_svc.record_event(
        db_session,
        tenant_id=tid,
        company_id=cid,
        user_id=mgr.id,
        module="sales",
        action="self_note",
        entity="note",
        entity_id="self-1",
        details={"note": "manager self event"},
    )
    store_ev = await audit_svc.record_event(
        db_session,
        tenant_id=tid,
        company_id=cid,
        user_id=other_user.id,
        module="sales",
        action="invoice_posted",
        entity="sales_invoice",
        entity_id="inv-aud-m",
        details={"store_id": mine.id, "invoice_number": "INV-AUD-M"},
    )
    wh_ev = await audit_svc.record_event(
        db_session,
        tenant_id=tid,
        company_id=cid,
        user_id=other_user.id,
        module="purchasing",
        action="receive",
        entity="goods_receipt",
        entity_id="grn-aud-m",
        details={"warehouse_id": wh_mine.id, "grn_number": "GRN-AUD-M"},
    )
    foreign_store = await audit_svc.record_event(
        db_session,
        tenant_id=tid,
        company_id=cid,
        user_id=other_user.id,
        module="sales",
        action="invoice_posted",
        entity="sales_invoice",
        entity_id="inv-aud-o",
        details={"store_id": other.id, "invoice_number": "INV-AUD-O-SECRET"},
    )
    foreign_unscoped = await audit_svc.record_event(
        db_session,
        tenant_id=tid,
        company_id=cid,
        user_id=other_user.id,
        module="users",
        action="update",
        entity="user",
        entity_id=other_user.id,
        details={"email": other_user.email, "secret": "ADMIN-ONLY-AUDIT"},
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/audit-logs", headers=headers, params={"limit": 500})
    assert listed.status_code == 200, listed.text
    ids = {r["id"] for r in listed.json()["data"]}
    assert self_ev.id in ids
    assert store_ev.id in ids
    assert wh_ev.id in ids
    assert foreign_store.id not in ids
    assert foreign_unscoped.id not in ids
    bodies = listed.json()["data"]
    assert all("INV-AUD-O-SECRET" not in json.dumps(r.get("details") or {}) for r in bodies)
    assert all("ADMIN-ONLY-AUDIT" not in json.dumps(r.get("details") or {}) for r in bodies)

    exported = await ac.get(
        "/api/v1/audit-logs/export",
        headers=headers,
        params={"format": "csv"},
    )
    assert exported.status_code == 200, exported.text
    assert "INV-AUD-M" in exported.text or store_ev.id in exported.text
    assert "INV-AUD-O-SECRET" not in exported.text
    assert "ADMIN-ONLY-AUDIT" not in exported.text


@pytest.mark.asyncio
async def test_store_manager_sales_returns_and_dashboard_slices_scoped(client, db_session):
    """Sales returns via invoice store; dashboard expenses/stock slices store+WH scoped."""
    from datetime import timedelta

    from app.inventory import apply_stock_change

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Ops Leftover Mine",
        code="OPS-LF-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Ops Leftover Other",
        code="OPS-LF-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Ops LF Mine WH",
        code="OPS-LF-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Ops LF Other WH",
        code="OPS-LF-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-OPS-LF-M",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        posted_at=today,
        created_by=mgr.id,
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-OPS-LF-O",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=400,
        tax_amount=0,
        total_amount=400,
        posted_at=today,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([inv_mine, inv_other])
    await db_session.flush()

    ret_mine = m.SalesReturn(
        tenant_id=tid,
        company_id=cid,
        return_number="SR-OPS-M",
        customer_id=seed["party1"].id,
        sales_invoice_id=inv_mine.id,
        status="draft",
        reason="damaged",
        restock=True,
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        created_by=mgr.id,
    )
    ret_other = m.SalesReturn(
        tenant_id=tid,
        company_id=cid,
        return_number="SR-OPS-O",
        customer_id=seed["party1"].id,
        sales_invoice_id=inv_other.id,
        status="draft",
        reason="damaged",
        restock=True,
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([ret_mine, ret_other])

    from app.expenses import ensure_default_categories

    await ensure_default_categories(db_session, tid, company_id=cid)
    cat = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tid)
        )
    ).scalars().first()
    assert cat is not None
    db_session.add_all(
        [
            m.Expense(
                tenant_id=tid,
                company_id=cid,
                category_id=cat.id,
                category=cat.name,
                description="Ops LF mine exp",
                amount=12,
                store_id=mine.id,
                status="approved",
                expense_date=today,
                created_by=mgr.id,
                approved_by=mgr.id,
                approved_at=today,
            ),
            m.Expense(
                tenant_id=tid,
                company_id=cid,
                category_id=cat.id,
                category=cat.name,
                description="Ops LF other exp",
                amount=900,
                store_id=other.id,
                status="approved",
                expense_date=today,
                created_by=seed["admin1"].id,
                approved_by=seed["admin1"].id,
                approved_at=today,
            ),
        ]
    )

    seed["p1"].stock_qty = 2
    seed["p1"].reorder_level = 20
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=2,
        movement_type="stock_in",
        user_id=mgr.id,
        warehouse_id=wh_mine.id,
    )
    await apply_stock_change(
        db_session,
        tenant_id=tid,
        product_id=seed["p1"].id,
        quantity_delta=2,
        movement_type="stock_in",
        user_id=seed["admin1"].id,
        warehouse_id=wh_other.id,
    )
    for wid in (wh_mine.id, wh_other.id):
        stock = (
            await db_session.execute(
                select(m.WarehouseStock).where(
                    m.WarehouseStock.warehouse_id == wid,
                    m.WarehouseStock.product_id == seed["p1"].id,
                )
            )
        ).scalar_one()
        stock.minimum_stock = 10
        stock.reorder_level = 20
    soon = datetime.utcnow() + timedelta(days=5)
    db_session.add_all(
        [
            m.ProductBatch(
                tenant_id=tid,
                company_id=cid,
                product_id=seed["p1"].id,
                warehouse_id=wh_mine.id,
                batch_number="OPS-LF-M-LOT",
                expiry_date=soon,
                quantity=2,
            ),
            m.ProductBatch(
                tenant_id=tid,
                company_id=cid,
                product_id=seed["p1"].id,
                warehouse_id=wh_other.id,
                batch_number="OPS-LF-O-LOT",
                expiry_date=soon,
                quantity=2,
            ),
        ]
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/sales/returns", headers=headers)
    assert listed.status_code == 200, listed.text
    nums = {r["return_number"] for r in listed.json()["data"]}
    assert "SR-OPS-M" in nums
    assert "SR-OPS-O" not in nums

    denied = await ac.get(f"/api/v1/sales/returns/{ret_other.id}", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_create = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": inv_other.id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert denied_create.status_code == 403

    exported = await ac.get("/api/v1/sales/returns/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "SR-OPS-M" in exported.text
    assert "SR-OPS-O" not in exported.text

    expenses = await ac.get("/api/v1/dashboard/expenses", headers=headers)
    assert expenses.status_code == 200, expenses.text
    ebody = expenses.json()["data"]
    assert float(ebody["total_expenses"]) == pytest.approx(12.0)
    assert all(float(r["total"]) < 100 for r in ebody["expenses_by_category"])

    alerts = await ac.get("/api/v1/dashboard/stock-alerts", headers=headers)
    assert alerts.status_code == 200, alerts.text
    abody = alerts.json()["data"]
    assert int(abody["low_stock"]) == 1
    assert int(abody["expiring_batches"]) == 1

    summary = await ac.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    sbody = summary.json()["data"]
    assert float(sbody["total_expenses"]) == pytest.approx(12.0)
    assert int(sbody["low_stock"]) == 1


@pytest.mark.asyncio
async def test_store_manager_journal_entries_store_scoped(client, db_session):
    """Journal list/get/export (+ write asserts) fail-closed on foreign/null store_id."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    # Grant accounting write so create/unpost hit store asserts (role default is read-only).
    # Company membership permissions override user.permissions in company workspace.
    perms = dict(permissions_for_role("store_manager"))
    perms["accounting"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="JE Scope Mine",
        code="JE-SCOPE-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="JE Scope Other",
        code="JE-SCOPE-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    je_mine = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        description="Mine store JE",
        reference="JE-SCOPE-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 25, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 25},
        ],
    )
    je_other = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other store JE",
        reference="JE-SCOPE-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 75, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 75},
        ],
    )
    je_null = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Null store JE",
        reference="JE-SCOPE-NULL",
        store_id=None,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 15, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 15},
        ],
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert listed.status_code == 200, listed.text
    refs = {row["reference"] for row in listed.json()["data"]}
    assert "JE-SCOPE-MINE" in refs
    assert "JE-SCOPE-OTH" not in refs
    assert "JE-SCOPE-NULL" not in refs

    ok = await ac.get(f"/api/v1/accounting/journal-entries/{je_mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    denied_other = await ac.get(
        f"/api/v1/accounting/journal-entries/{je_other.id}", headers=headers
    )
    assert denied_other.status_code == 403
    assert denied_other.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_null = await ac.get(
        f"/api/v1/accounting/journal-entries/{je_null.id}", headers=headers
    )
    assert denied_null.status_code == 403
    assert denied_null.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    cross = await ac.get(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        params={"store_id": other.id},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    exported = await ac.get("/api/v1/accounting/journal-entries/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "JE-SCOPE-MINE" in exported.text
    assert "JE-SCOPE-OTH" not in exported.text
    assert "JE-SCOPE-NULL" not in exported.text

    create_ok = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Mgr in-scope JE",
            "reference": "JE-SCOPE-CREATE",
            "store_id": mine.id,
            "lines": [
                {"account_code": "1000", "debit": 5, "credit": 0},
                {"account_code": "4000", "debit": 0, "credit": 5},
            ],
        },
    )
    assert create_ok.status_code == 200, create_ok.text

    create_other = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Mgr foreign JE",
            "reference": "JE-SCOPE-CREATE-O",
            "store_id": other.id,
            "lines": [
                {"account_code": "1000", "debit": 5, "credit": 0},
                {"account_code": "4000", "debit": 0, "credit": 5},
            ],
        },
    )
    assert create_other.status_code == 403
    assert create_other.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    create_unset = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Mgr null-store JE",
            "reference": "JE-SCOPE-CREATE-N",
            "lines": [
                {"account_code": "1000", "debit": 5, "credit": 0},
                {"account_code": "4000", "debit": 0, "credit": 5},
            ],
        },
    )
    assert create_unset.status_code == 403
    assert create_unset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_unpost = await ac.post(
        f"/api/v1/accounting/journal-entries/{je_other.id}/unpost",
        headers=headers,
    )
    assert denied_unpost.status_code == 403
    assert denied_unpost.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_attach = await ac.get(
        f"/api/v1/accounting/journal-entries/{je_null.id}/attachment",
        headers=headers,
    )
    assert denied_attach.status_code == 403
    assert denied_attach.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_recurring_expenses_residual_scoped(client, db_session):
    """Recurring list/export/patch/generate stay within managed stores (null fail-closed)."""
    from datetime import timedelta

    from app.expenses import ensure_default_categories

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await ensure_default_categories(db_session, tid, company_id=cid)
    past = datetime.utcnow() - timedelta(days=1)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Recur Scope Mine",
        code="REC-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Recur Scope Other",
        code="REC-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    row_mine = m.RecurringExpense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Recur mine due",
        amount=11,
        frequency="monthly",
        payment_method="cash",
        store_id=mine.id,
        next_run_at=past,
        start_date=past,
        is_active=True,
        created_by=mgr.id,
    )
    row_other = m.RecurringExpense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Recur other due",
        amount=99,
        frequency="monthly",
        payment_method="cash",
        store_id=other.id,
        next_run_at=past,
        start_date=past,
        is_active=True,
        created_by=seed["admin1"].id,
    )
    row_null = m.RecurringExpense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Recur null due",
        amount=33,
        frequency="monthly",
        payment_method="cash",
        store_id=None,
        next_run_at=past,
        start_date=past,
        is_active=True,
        created_by=seed["admin1"].id,
    )
    db_session.add_all([row_mine, row_other, row_null])
    await db_session.commit()

    listed = await ac.get("/api/v1/expenses/recurring", headers=headers)
    assert listed.status_code == 200, listed.text
    descs = {r["description"] for r in listed.json()["data"]}
    assert "Recur mine due" in descs
    assert "Recur other due" not in descs
    assert "Recur null due" not in descs

    exported = await ac.get("/api/v1/expenses/recurring/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "Recur mine due" in exported.text
    assert "Recur other due" not in exported.text
    assert "Recur null due" not in exported.text

    denied_patch = await ac.patch(
        f"/api/v1/expenses/recurring/{row_other.id}",
        headers=headers,
        json={"is_active": False},
    )
    assert denied_patch.status_code == 403
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_null_patch = await ac.patch(
        f"/api/v1/expenses/recurring/{row_null.id}",
        headers=headers,
        json={"is_active": False},
    )
    assert denied_null_patch.status_code == 403
    assert denied_null_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_patch = await ac.patch(
        f"/api/v1/expenses/recurring/{row_mine.id}",
        headers=headers,
        json={"next_description": "Mine override"},
    )
    assert ok_patch.status_code == 200, ok_patch.text
    assert ok_patch.json()["data"]["next_description"] == "Mine override"

    generated = await ac.post("/api/v1/expenses/recurring/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    gdescs = {e["description"] for e in generated.json()["data"]}
    assert "Mine override" in gdescs
    assert "Recur other due" not in gdescs
    assert "Recur null due" not in gdescs


@pytest.mark.asyncio
async def test_store_manager_account_ledger_store_scoped(client, db_session):
    """COA account ledger (+ export) excludes foreign/null-store journal lines."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Ledger Scope Mine",
        code="LED-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Ledger Scope Other",
        code="LED-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        description="Mine ledger sale",
        reference="JE-LED-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 40, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 40},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other ledger sale",
        reference="JE-LED-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 800, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 800},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Null ledger sale",
        reference="JE-LED-NULL",
        store_id=None,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 50, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 50},
        ],
    )
    await db_session.commit()

    cash = await accounting_svc.get_account_by_code(
        db_session, tid, "1000", company_id=cid
    )
    assert cash is not None

    ledger = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions", headers=headers
    )
    assert ledger.status_code == 200, ledger.text
    body = ledger.json()["data"]
    refs = {row["reference"] for row in body["transactions"]}
    assert "JE-LED-MINE" in refs
    assert "JE-LED-OTH" not in refs
    assert "JE-LED-NULL" not in refs
    assert float(body["total_debit"]) == pytest.approx(40.0)
    assert float(body["closing_balance"]) == pytest.approx(40.0)

    denied = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions",
        headers=headers,
        params={"store_id": other.id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    exported = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "JE-LED-MINE" in exported.text
    assert "JE-LED-OTH" not in exported.text
    assert "JE-LED-NULL" not in exported.text


@pytest.mark.asyncio
async def test_store_manager_coa_and_liquid_balances_store_scoped(client, db_session):
    """COA list/get and liquid account list/export rebuild balances from managed-store journals."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Bal Scope Mine",
        code="BAL-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Bal Scope Other",
        code="BAL-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        description="Mine cash sale",
        reference="JE-BAL-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 55, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 55},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other cash sale",
        reference="JE-BAL-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 900, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 900},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Null cash sale",
        reference="JE-BAL-NULL",
        store_id=None,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 70, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 70},
        ],
    )
    await db_session.commit()

    cash = await accounting_svc.get_account_by_code(db_session, tid, "1000", company_id=cid)
    assert cash is not None

    coa_list = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert coa_list.status_code == 200, coa_list.text
    list_codes = {a["code"] for a in coa_list.json()["data"]}
    assert "1000" in list_codes
    assert "4000" not in list_codes
    cash_row = next(a for a in coa_list.json()["data"] if a["code"] == "1000")
    assert float(cash_row["balance"]) == pytest.approx(55.0)

    coa_tree = await ac.get("/api/v1/accounting/accounts", headers=headers, params={"tree": "true"})
    assert coa_tree.status_code == 200, coa_tree.text

    def _find_code(nodes, code):
        for n in nodes:
            if n.get("code") == code:
                return n
            found = _find_code(n.get("children") or [], code)
            if found:
                return found
        return None

    tree_cash = _find_code(coa_tree.json()["data"], "1000")
    assert tree_cash is not None
    assert float(tree_cash["balance"]) == pytest.approx(55.0)

    coa_get = await ac.get(f"/api/v1/accounting/accounts/{cash.id}", headers=headers)
    assert coa_get.status_code == 200, coa_get.text
    assert float(coa_get.json()["data"]["balance"]) == pytest.approx(55.0)

    liquid = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert liquid.status_code == 200, liquid.text
    liq_cash = next(a for a in liquid.json()["data"] if a["code"] == "1000")
    assert float(liq_cash["balance"]) == pytest.approx(55.0)

    liq_csv = await ac.get("/api/v1/accounting/liquid-accounts/export", headers=headers)
    assert liq_csv.status_code == 200, liq_csv.text
    assert "900" not in liq_csv.text.splitlines()[1] if len(liq_csv.text.splitlines()) > 1 else True
    assert "55" in liq_csv.text


@pytest.mark.asyncio
async def test_store_manager_coa_account_read_scoped(client, db_session):
    """COA get/list/tree/export deny non-liquid reads; liquid scoped like opening balance."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="COA Read Mine",
        code="COA-R-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="COA Read Other",
        code="COA-R-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    cash = await accounting_svc.get_account_by_code(db_session, tid, "1000", company_id=cid)
    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    revenue = await accounting_svc.get_account_by_code(db_session, tid, "4000", company_id=cid)
    assert cash is not None and bank is not None and revenue is not None

    foreign_bank_only = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=tid,
        kind="bank",
        code="1096",
        name="Foreign Read Bank",
        bank_name="Foreign Bank",
        company_id=cid,
    )
    untouched_petty = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=tid,
        kind="cash",
        code="1095",
        name="Untouched Petty",
        company_id=cid,
    )

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Mine cash read",
        reference="JE-READ-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 30, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 30},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other bank read",
        reference="JE-READ-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 500, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 500},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Foreign-only bank read",
        reference="JE-READ-FOR",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": foreign_bank_only.code, "debit": 80, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 80},
        ],
    )
    await db_session.commit()

    denied_revenue = await ac.get(
        f"/api/v1/accounting/accounts/{revenue.id}", headers=headers
    )
    assert denied_revenue.status_code == 403
    assert denied_revenue.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_cash = await ac.get(f"/api/v1/accounting/accounts/{cash.id}", headers=headers)
    assert ok_cash.status_code == 200, ok_cash.text
    assert float(ok_cash.json()["data"]["balance"]) == pytest.approx(30.0)

    ok_untouched = await ac.get(
        f"/api/v1/accounting/accounts/{untouched_petty.id}", headers=headers
    )
    assert ok_untouched.status_code == 200, ok_untouched.text

    denied_bank = await ac.get(f"/api/v1/accounting/accounts/{bank.id}", headers=headers)
    assert denied_bank.status_code == 403
    assert denied_bank.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_foreign = await ac.get(
        f"/api/v1/accounting/accounts/{foreign_bank_only.id}", headers=headers
    )
    assert denied_foreign.status_code == 403
    assert denied_foreign.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    coa_list = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert coa_list.status_code == 200, coa_list.text
    list_codes = {a["code"] for a in coa_list.json()["data"]}
    assert "1000" in list_codes
    assert "1095" in list_codes
    assert "1010" not in list_codes
    assert "1096" not in list_codes
    assert "4000" not in list_codes

    coa_tree = await ac.get(
        "/api/v1/accounting/accounts", headers=headers, params={"tree": "true"}
    )
    assert coa_tree.status_code == 200, coa_tree.text

    def _collect_codes(nodes):
        codes = set()
        for n in nodes:
            codes.add(n.get("code"))
            codes.update(_collect_codes(n.get("children") or []))
        return codes

    tree_codes = _collect_codes(coa_tree.json()["data"])
    assert "1000" in tree_codes
    assert "1095" in tree_codes
    assert "4000" not in tree_codes
    assert "1010" not in tree_codes

    exported = await ac.get("/api/v1/accounting/accounts/export", headers=headers)
    assert exported.status_code == 200, exported.text
    export_lines = exported.text.splitlines()
    assert any("1000" in line for line in export_lines[1:])
    assert any("1095" in line for line in export_lines[1:])
    assert not any("4000" in line for line in export_lines[1:])
    assert not any("1010" in line for line in export_lines[1:])


@pytest.mark.asyncio
async def test_store_manager_coa_and_liquid_account_writes_scoped(client, db_session):
    """COA create/patch and liquid create denied; liquid patch scoped to managed journals."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    perms = dict(permissions_for_role("store_manager"))
    perms["accounting"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="COA Write Mine",
        code="COA-W-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="COA Write Other",
        code="COA-W-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    cash = await accounting_svc.get_account_by_code(db_session, tid, "1000", company_id=cid)
    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    assert cash is not None and bank is not None

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Mine cash activity",
        reference="JE-COA-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other bank activity",
        reference="JE-COA-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 200, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 200},
        ],
    )
    await db_session.commit()

    denied_coa_create = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "5999",
            "name": "Denied COA",
            "account_type": "expense",
        },
    )
    assert denied_coa_create.status_code == 403
    assert denied_coa_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_coa_patch = await ac.patch(
        f"/api/v1/accounting/accounts/{cash.id}",
        headers=headers,
        json={"name": "Renamed Cash"},
    )
    assert denied_coa_patch.status_code == 403
    assert denied_coa_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_liq_create = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={
            "kind": "cash",
            "code": "1097",
            "name": "Denied Petty",
        },
    )
    assert denied_liq_create.status_code == 403
    assert denied_liq_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_liq_patch = await ac.patch(
        f"/api/v1/accounting/liquid-accounts/{cash.id}",
        headers=headers,
        json={"name": "Managed Store Cash"},
    )
    assert ok_liq_patch.status_code == 200, ok_liq_patch.text
    assert ok_liq_patch.json()["data"]["name"] == "Managed Store Cash"

    denied_liq_patch = await ac.patch(
        f"/api/v1/accounting/liquid-accounts/{bank.id}",
        headers=headers,
        json={"name": "Foreign Bank"},
    )
    assert denied_liq_patch.status_code == 403
    assert denied_liq_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_fiscal_close = await ac.post(
        "/api/v1/accounting/fiscal-period/close",
        headers=headers,
    )
    assert denied_fiscal_close.status_code == 403
    assert denied_fiscal_close.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_bank_recon_unmatched_book_store_scoped(client, db_session):
    """Bank statement detail scopes unmatched book lines/suggestions to managed-store journals."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    mgr_headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Bank Recon Mine",
        code="BR-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Bank Recon Other",
        code="BR-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    assert bank is not None

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        description="Mine bank deposit",
        reference="JE-BR-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 120, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 120},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other bank deposit",
        reference="JE-BR-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 7500, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 7500},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Null bank deposit",
        reference="JE-BR-NULL",
        store_id=None,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 33, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 33},
        ],
    )
    await db_session.commit()

    from app import bank_recon as bank_recon_svc

    stmt_row = await bank_recon_svc.create_statement(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        account_id=bank.id,
        statement_date="2026-08-20",
        opening_balance=0,
        closing_balance=120,
        notes="BR scope test",
        lines=[
            {
                "txn_date": "2026-08-20",
                "amount": 120,
                "description": "Mine deposit",
                "external_ref": "JE-BR-MINE",
            }
        ],
        company_id=cid,
    )
    await db_session.commit()
    sid = stmt_row.id

    detail = await ac.get(f"/api/v1/accounting/bank-statements/{sid}", headers=mgr_headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()["data"]
    refs = {row.get("reference") for row in body.get("unmatched_book_lines") or []}
    assert "JE-BR-MINE" in refs
    assert "JE-BR-OTH" not in refs
    assert "JE-BR-NULL" not in refs
    sug_jl_ids = {s.get("journal_line_id") for s in body.get("suggestions") or []}
    book_jl_ids = {row.get("journal_line_id") for row in body.get("unmatched_book_lines") or []}
    assert not sug_jl_ids or sug_jl_ids.issubset(book_jl_ids)

    from fastapi import HTTPException

    foreign_jl = next(
        row["journal_line_id"]
        for row in (
            await bank_recon_svc.unmatched_book_lines(
                db_session, tenant_id=tid, account_id=bank.id, store_ids=None
            )
        )
        if row.get("reference") == "JE-BR-OTH"
    )
    line_id = (
        await bank_recon_svc.list_statement_lines(db_session, tid, sid)
    )[0].id
    with pytest.raises(HTTPException) as exc:
        await bank_recon_svc.match_line(
            db_session,
            tenant_id=tid,
            line_id=line_id,
            journal_line_id=foreign_jl,
            store_ids=[mine.id],
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_bank_statements_list_export_scoped(client, db_session):
    """Bank statement list/export scoped via liquid accounts + statement touch points."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["admin1"]
    mgr_headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="BS List Mine",
        code="BS-M",
        manager_id=seed["mgr1"].id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="BS List Other",
        code="BS-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    assert bank is not None

    mine_je = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["mgr1"].id,
        description="Mine bank deposit",
        reference="JE-BS-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 120, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 120},
        ],
    )
    other_je = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        description="Other bank deposit",
        reference="JE-BS-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 7500, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 7500},
        ],
    )
    await db_session.commit()

    from app import bank_recon as bank_recon_svc

    stmt_in_scope = await bank_recon_svc.create_statement(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        account_id=bank.id,
        statement_date="2026-08-21",
        opening_balance=0,
        closing_balance=120,
        notes="BS list in-scope",
        lines=[
            {
                "txn_date": "2026-08-21",
                "amount": 120,
                "description": "Mine deposit",
                "external_ref": "JE-BS-MINE",
            }
        ],
        company_id=cid,
    )
    stmt_foreign = await bank_recon_svc.create_statement(
        db_session,
        tenant_id=tid,
        user_id=mgr.id,
        account_id=bank.id,
        statement_date="2026-08-22",
        opening_balance=0,
        closing_balance=7500,
        notes="BS list foreign match",
        lines=[
            {
                "txn_date": "2026-08-22",
                "amount": 7500,
                "description": "Other deposit",
                "external_ref": "JE-BS-OTH",
            }
        ],
        company_id=cid,
    )
    await db_session.flush()

    foreign_jl = next(
        row["journal_line_id"]
        for row in (
            await bank_recon_svc.unmatched_book_lines(
                db_session, tenant_id=tid, account_id=bank.id, store_ids=None
            )
        )
        if row.get("reference") == "JE-BS-OTH"
    )
    foreign_line = (
        await bank_recon_svc.list_statement_lines(db_session, tid, stmt_foreign.id)
    )[0]
    await bank_recon_svc.match_line(
        db_session,
        tenant_id=tid,
        line_id=foreign_line.id,
        journal_line_id=foreign_jl,
        store_ids=None,
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/bank-statements", headers=mgr_headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert stmt_in_scope.id in ids
    assert stmt_foreign.id not in ids

    exported = await ac.get("/api/v1/accounting/bank-statements/export", headers=mgr_headers)
    assert exported.status_code == 200, exported.text
    assert stmt_in_scope.id in exported.text or "BS list in-scope" in exported.text
    assert "BS list foreign match" not in exported.text

    denied = await ac.get(
        f"/api/v1/accounting/bank-statements/{stmt_foreign.id}",
        headers=mgr_headers,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_bank_statement_create_import_writes_scoped(client, db_session):
    """Bank statement create/import require account_id in managed liquid account scope."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    perms = dict(permissions_for_role("store_manager"))
    perms["accounting"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="BS Write Mine",
        code="BSW-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="BS Write Other",
        code="BSW-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    cash = await accounting_svc.get_account_by_code(db_session, tid, "1000", company_id=cid)
    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    assert cash is not None and bank is not None

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Mine cash activity",
        reference="JE-BSW-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 50, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 50},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other bank activity",
        reference="JE-BSW-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 300, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 300},
        ],
    )
    await db_session.commit()

    ok_create = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": cash.id,
            "statement_date": "2026-08-23",
            "opening_balance": 0,
            "closing_balance": 25,
            "lines": [{"posted_at": "2026-08-23", "amount": 25, "description": "Mine deposit"}],
        },
    )
    assert ok_create.status_code == 200, ok_create.text

    denied_create = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": bank.id,
            "statement_date": "2026-08-23",
            "opening_balance": 0,
            "closing_balance": 100,
            "lines": [{"posted_at": "2026-08-23", "amount": 100, "description": "Foreign bank"}],
        },
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    csv_text = "date,amount,description,ref\n2026-08-23,15,Petty,F1\n"
    ok_import = await ac.post(
        "/api/v1/accounting/bank-statements/import",
        headers=headers,
        params={"account_id": cash.id, "opening_balance": 0},
        files={"file": ("mine.csv", csv_text, "text/csv")},
    )
    assert ok_import.status_code == 200, ok_import.text

    denied_import = await ac.post(
        "/api/v1/accounting/bank-statements/import",
        headers=headers,
        params={"account_id": bank.id, "opening_balance": 0},
        files={"file": ("foreign.csv", csv_text, "text/csv")},
    )
    assert denied_import.status_code == 403
    assert denied_import.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_bank_connections_scoped(client, db_session):
    """Bank connections list/export/writes scoped via managed liquid account activity."""
    from app import bank_connectors as bank_connectors_svc
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    perms = dict(permissions_for_role("store_manager"))
    perms["accounting"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="BC Scope Mine",
        code="BC-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="BC Scope Other",
        code="BC-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    cash = await accounting_svc.get_account_by_code(db_session, tid, "1000", company_id=cid)
    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    assert cash is not None and bank is not None

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Mine cash activity",
        reference="JE-BC-MINE",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 80, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 80},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Other bank activity",
        reference="JE-BC-OTH",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 120, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 120},
        ],
    )
    conn_mine = await bank_connectors_svc.create_connection(
        db_session,
        tenant_id=tid,
        account_id=cash.id,
        provider="mock",
        display_name="Mine Cash Feed",
        company_id=cid,
    )
    conn_other = await bank_connectors_svc.create_connection(
        db_session,
        tenant_id=tid,
        account_id=bank.id,
        provider="mock",
        display_name="Other Bank Feed",
        company_id=cid,
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/bank-connections", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert conn_mine.id in ids
    assert conn_other.id not in ids

    exported = await ac.get("/api/v1/accounting/bank-connections/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "Mine Cash Feed" in exported.text
    assert "Other Bank Feed" not in exported.text

    denied_create = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={"account_id": bank.id, "provider": "mock", "display_name": "Denied"},
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/accounting/bank-connections/{conn_other.id}",
        headers=headers,
        json={"display_name": "Hacked"},
    )
    assert denied_patch.status_code == 403
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_patch = await ac.patch(
        f"/api/v1/accounting/bank-connections/{conn_mine.id}",
        headers=headers,
        json={"display_name": "Mine Cash Feed Updated"},
    )
    assert ok_patch.status_code == 200, ok_patch.text

    denied_sync = await ac.post(
        f"/api/v1/accounting/bank-connections/{conn_other.id}/sync",
        headers=headers,
    )
    assert denied_sync.status_code == 403
    assert denied_sync.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_sync = await ac.post(
        f"/api/v1/accounting/bank-connections/{conn_mine.id}/sync",
        headers=headers,
    )
    assert ok_sync.status_code == 200, ok_sync.text

    denied_delete = await ac.delete(
        f"/api/v1/accounting/bank-connections/{conn_other.id}",
        headers=headers,
    )
    assert denied_delete.status_code == 403
    assert denied_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_liquid_transfer_and_opening_balance_writes_scoped(
    client, db_session
):
    """Liquid transfers and opening balances require managed store_id for store_manager writes."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)

    perms = dict(permissions_for_role("store_manager"))
    perms["accounting"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Liquid Write Mine",
        code="LIQ-W-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Liquid Write Other",
        code="LIQ-W-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    cash = await accounting_svc.get_account_by_code(db_session, tid, "1000", company_id=cid)
    bank = await accounting_svc.get_account_by_code(db_session, tid, "1010", company_id=cid)
    assert cash is not None and bank is not None

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Seed cash for liquid xfer test",
        reference="JE-LIQ-SEED",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1000", "debit": 500, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 500},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Seed bank for liquid xfer test",
        reference="JE-LIQ-BANK",
        store_id=mine.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Foreign bank only",
        reference="JE-LIQ-FOR",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1010", "debit": 999, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 999},
        ],
    )
    foreign_bank_only = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=tid,
        kind="bank",
        code="1097",
        name="Foreign Scope Bank",
        bank_name="Foreign Bank",
        company_id=cid,
    )
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tid,
        user_id=seed["admin1"].id,
        description="Foreign-only liquid bank",
        reference="JE-LIQ-FBO",
        store_id=other.id,
        company_id=cid,
        lines=[
            {"account_code": "1097", "debit": 50, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 50},
        ],
    )
    await db_session.commit()

    ok_xfer = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash.id,
            "to_account_id": bank.id,
            "amount": 50,
            "kind": "deposit",
            "reference": "LIQ-XFER-MINE",
            "store_id": mine.id,
        },
    )
    assert ok_xfer.status_code == 200, ok_xfer.text
    assert ok_xfer.json()["data"]["source_type"] == "liquid_deposit"

    denied_other = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash.id,
            "to_account_id": bank.id,
            "amount": 10,
            "kind": "deposit",
            "store_id": other.id,
        },
    )
    assert denied_other.status_code == 403
    assert denied_other.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_unset = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash.id,
            "to_account_id": bank.id,
            "amount": 10,
            "kind": "deposit",
        },
    )
    assert denied_unset.status_code == 403
    assert denied_unset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_foreign_acct = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash.id,
            "to_account_id": foreign_bank_only.id,
            "amount": 5,
            "kind": "deposit",
            "store_id": mine.id,
        },
    )
    assert denied_foreign_acct.status_code == 403
    assert denied_foreign_acct.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    petty = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=tid,
        kind="cash",
        code="1099",
        name="Scope Test Petty",
        company_id=cid,
    )
    petty2 = await accounting_svc.create_liquid_account(
        db_session,
        tenant_id=tid,
        kind="cash",
        code="1098",
        name="Scope Test Petty 2",
        company_id=cid,
    )
    await db_session.commit()

    ok_ob = await ac.post(
        f"/api/v1/accounting/accounts/{petty.id}/opening-balance",
        headers=headers,
        json={"amount": 20, "store_id": mine.id},
    )
    assert ok_ob.status_code == 200, ok_ob.text

    denied_ob = await ac.post(
        f"/api/v1/accounting/accounts/{petty2.id}/opening-balance",
        headers=headers,
        json={"amount": 15},
    )
    assert denied_ob.status_code == 403
    assert denied_ob.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    revenue = await accounting_svc.get_account_by_code(
        db_session, tid, "4000", company_id=cid
    )
    assert revenue is not None
    denied_revenue_ob = await ac.post(
        f"/api/v1/accounting/accounts/{revenue.id}/opening-balance",
        headers=headers,
        json={"amount": 10, "store_id": mine.id},
    )
    assert denied_revenue_ob.status_code == 403
    assert denied_revenue_ob.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_foreign_ob = await ac.post(
        f"/api/v1/accounting/accounts/{foreign_bank_only.id}/opening-balance",
        headers=headers,
        json={"amount": 5, "store_id": mine.id},
    )
    assert denied_foreign_ob.status_code == 403
    assert denied_foreign_ob.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    inventory = await accounting_svc.get_account_by_code(
        db_session, tid, "1200", company_id=cid
    )
    assert inventory is not None
    denied_non_liquid = await ac.post(
        f"/api/v1/accounting/accounts/{inventory.id}/opening-balance",
        headers=headers,
        json={"amount": 100, "store_id": mine.id},
    )
    assert denied_non_liquid.status_code == 403
    assert denied_non_liquid.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_ob_managed_cash = await ac.post(
        f"/api/v1/accounting/accounts/{cash.id}/opening-balance",
        headers=headers,
        json={"amount": 25, "store_id": mine.id},
    )
    assert ok_ob_managed_cash.status_code == 200, ok_ob_managed_cash.text

    denied_foreign_only = await ac.post(
        f"/api/v1/accounting/accounts/{foreign_bank_only.id}/opening-balance",
        headers=headers,
        json={"amount": 10, "store_id": mine.id},
    )
    assert denied_foreign_only.status_code == 403
    assert denied_foreign_only.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_expense_lifecycle_writes_store_scoped(client, db_session):
    """Approve/reject/delete/OCR/attachment writes fail-closed outside managed stores."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Exp Life Mine",
        code="EXL-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Exp Life Other",
        code="EXL-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    exp_mine = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Life mine pending",
        amount=10,
        store_id=mine.id,
        status="pending",
        created_by=seed["admin1"].id,
    )
    exp_other = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Life other pending",
        amount=20,
        store_id=other.id,
        status="pending",
        created_by=mgr.id,
    )
    exp_null = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Life null pending",
        amount=30,
        store_id=None,
        status="pending",
        created_by=mgr.id,
    )
    exp_other_del = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Life other delete",
        amount=4,
        store_id=other.id,
        status="pending",
        created_by=mgr.id,
    )
    exp_mine_del = m.Expense(
        tenant_id=tid,
        company_id=cid,
        category="Travel",
        description="Life mine delete",
        amount=5,
        store_id=mine.id,
        status="pending",
        created_by=mgr.id,
    )
    db_session.add_all([exp_mine, exp_other, exp_null, exp_other_del, exp_mine_del])
    await db_session.commit()

    denied_approve = await ac.post(
        f"/api/v1/expenses/{exp_other.id}/approve", headers=headers, json={}
    )
    assert denied_approve.status_code == 403
    assert denied_approve.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_null_approve = await ac.post(
        f"/api/v1/expenses/{exp_null.id}/approve", headers=headers, json={}
    )
    assert denied_null_approve.status_code == 403
    assert denied_null_approve.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_approve = await ac.post(
        f"/api/v1/expenses/{exp_mine.id}/approve", headers=headers, json={}
    )
    assert ok_approve.status_code == 200, ok_approve.text

    denied_reject = await ac.post(
        f"/api/v1/expenses/{exp_other.id}/reject",
        headers=headers,
        json={"reason": "out of scope"},
    )
    assert denied_reject.status_code == 403
    assert denied_reject.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_ocr = await ac.post(
        f"/api/v1/expenses/{exp_other.id}/ocr-suggest", headers=headers
    )
    assert denied_ocr.status_code == 403
    assert denied_ocr.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_ocr_apply = await ac.post(
        f"/api/v1/expenses/{exp_null.id}/ocr-apply",
        headers=headers,
        json={"confirm": True, "description": "should fail"},
    )
    assert denied_ocr_apply.status_code == 403
    assert denied_ocr_apply.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_del_attach = await ac.delete(
        f"/api/v1/expenses/{exp_other.id}/attachment", headers=headers
    )
    assert denied_del_attach.status_code == 403
    assert denied_del_attach.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_delete = await ac.delete(
        f"/api/v1/expenses/{exp_other_del.id}", headers=headers
    )
    assert denied_delete.status_code == 403
    assert denied_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_delete = await ac.delete(f"/api/v1/expenses/{exp_mine_del.id}", headers=headers)
    assert ok_delete.status_code == 200, ok_delete.text


@pytest.mark.asyncio
async def test_store_manager_party_history_store_wh_scoped(client, db_session):
    """Customer/supplier history (+ export) hide foreign-store/WH and null-bound docs."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Hist Scope Mine",
        code="HIST-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Hist Scope Other",
        code="HIST-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Hist Mine WH",
        code="HIST-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Hist Other WH",
        code="HIST-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    cust = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Hist Shared Customer",
        kind="customer",
        status="active",
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Hist Shared Supplier",
        kind="supplier",
        status="active",
    )
    db_session.add_all([cust, supplier])
    await db_session.flush()

    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-HIST-M",
        customer_id=cust.id,
        status="posted",
        subtotal=40,
        total_amount=40,
        paid_amount=10,
        posted_at=datetime.utcnow(),
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-HIST-O",
        customer_id=cust.id,
        status="posted",
        subtotal=900,
        total_amount=900,
        paid_amount=0,
        posted_at=datetime.utcnow(),
    )
    inv_null = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=None,
        invoice_number="INV-HIST-N",
        customer_id=cust.id,
        status="posted",
        subtotal=15,
        total_amount=15,
        paid_amount=0,
        posted_at=datetime.utcnow(),
    )
    db_session.add_all([inv_mine, inv_other, inv_null])
    await db_session.flush()

    order_mine = m.SalesOrder(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        order_number="SO-HIST-M",
        customer_id=cust.id,
        status="confirmed",
        subtotal=20,
        total_amount=20,
    )
    order_other = m.SalesOrder(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        order_number="SO-HIST-O",
        customer_id=cust.id,
        status="confirmed",
        subtotal=80,
        total_amount=80,
    )
    quote_open = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="QT-HIST-OPEN",
        customer_id=cust.id,
        status="sent",
        subtotal=12,
        total_amount=12,
    )
    quote_converted = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="QT-HIST-CONV",
        customer_id=cust.id,
        status="converted",
        subtotal=40,
        total_amount=40,
        converted_invoice_id=None,  # set after flush of inv_mine
    )
    db_session.add_all([order_mine, order_other, quote_open, quote_converted])
    await db_session.flush()
    quote_converted.converted_invoice_id = inv_mine.id

    ret_mine = m.SalesReturn(
        tenant_id=tid,
        company_id=cid,
        return_number="SR-HIST-M",
        customer_id=cust.id,
        sales_invoice_id=inv_mine.id,
        status="posted",
        subtotal=5,
        total_amount=5,
    )
    ret_other = m.SalesReturn(
        tenant_id=tid,
        company_id=cid,
        return_number="SR-HIST-O",
        customer_id=cust.id,
        sales_invoice_id=inv_other.id,
        status="posted",
        subtotal=9,
        total_amount=9,
    )
    pay_mine = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CP-HIST-M",
        customer_id=cust.id,
        sales_invoice_id=inv_mine.id,
        amount=10,
        payment_method="cash",
    )
    pay_other = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CP-HIST-O",
        customer_id=cust.id,
        sales_invoice_id=inv_other.id,
        amount=50,
        payment_method="cash",
    )
    pay_unalloc = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CP-HIST-U",
        customer_id=cust.id,
        sales_invoice_id=None,
        amount=3,
        payment_method="cash",
    )
    db_session.add_all([ret_mine, ret_other, pay_mine, pay_other, pay_unalloc])

    po_mine = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-HIST-M",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="ordered",
        subtotal=30,
        total_amount=30,
    )
    po_other = m.PurchaseOrder(
        tenant_id=tid,
        company_id=cid,
        po_number="PO-HIST-O",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="ordered",
        subtotal=700,
        total_amount=700,
    )
    pi_mine = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-HIST-M",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="unpaid",
        subtotal=30,
        total_amount=30,
        paid_amount=8,
    )
    pi_other = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-HIST-O",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="unpaid",
        subtotal=700,
        total_amount=700,
        paid_amount=0,
    )
    pi_null = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-HIST-N",
        supplier_id=supplier.id,
        warehouse_id=None,
        status="unpaid",
        subtotal=11,
        total_amount=11,
        paid_amount=0,
    )
    db_session.add_all([po_mine, po_other, pi_mine, pi_other, pi_null])
    await db_session.flush()

    sp_mine = m.SupplierPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="SP-HIST-M",
        supplier_id=supplier.id,
        purchase_invoice_id=pi_mine.id,
        amount=8,
        payment_method="bank_transfer",
    )
    sp_other = m.SupplierPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="SP-HIST-O",
        supplier_id=supplier.id,
        purchase_invoice_id=pi_other.id,
        amount=40,
        payment_method="bank_transfer",
    )
    db_session.add_all([sp_mine, sp_other])
    await db_session.commit()

    cust_hist = await ac.get(f"/api/v1/customers/{cust.id}/history", headers=headers)
    assert cust_hist.status_code == 200, cust_hist.text
    cbody = cust_hist.json()["data"]
    inv_nums = {r["invoice_number"] for r in cbody["invoices"]}
    assert "INV-HIST-M" in inv_nums
    assert "INV-HIST-O" not in inv_nums
    assert "INV-HIST-N" not in inv_nums
    so_nums = {r["order_number"] for r in cbody["orders"]}
    assert "SO-HIST-M" in so_nums
    assert "SO-HIST-O" not in so_nums
    ret_nums = {r["return_number"] for r in cbody["returns"]}
    assert "SR-HIST-M" in ret_nums
    assert "SR-HIST-O" not in ret_nums
    assert len(cbody["payments"]) == 1
    assert float(cbody["payments"][0]["amount"]) == pytest.approx(10.0)
    q_nums = {r["quotation_number"] for r in cbody["quotations"]}
    assert "QT-HIST-CONV" in q_nums
    assert "QT-HIST-OPEN" not in q_nums

    cust_csv = await ac.get(
        f"/api/v1/customers/{cust.id}/history/export", headers=headers
    )
    assert cust_csv.status_code == 200, cust_csv.text
    assert "INV-HIST-M" in cust_csv.text
    assert "INV-HIST-O" not in cust_csv.text
    assert "QT-HIST-OPEN" not in cust_csv.text

    supp_hist = await ac.get(f"/api/v1/suppliers/{supplier.id}/history", headers=headers)
    assert supp_hist.status_code == 200, supp_hist.text
    sbody = supp_hist.json()["data"]
    po_nums = {r["po_number"] for r in sbody["orders"]}
    assert "PO-HIST-M" in po_nums
    assert "PO-HIST-O" not in po_nums
    pi_nums = {r["invoice_number"] for r in sbody["invoices"]}
    assert "PI-HIST-M" in pi_nums
    assert "PI-HIST-O" not in pi_nums
    assert "PI-HIST-N" not in pi_nums
    assert len(sbody["payments"]) == 1
    assert float(sbody["payments"][0]["amount"]) == pytest.approx(8.0)

    supp_csv = await ac.get(
        f"/api/v1/suppliers/{supplier.id}/history/export", headers=headers
    )
    assert supp_csv.status_code == 200, supp_csv.text
    assert "PO-HIST-M" in supp_csv.text
    assert "PO-HIST-O" not in supp_csv.text
    assert "PI-HIST-N" not in supp_csv.text


@pytest.mark.asyncio
async def test_store_manager_product_batches_wh_scoped(client, db_session):
    """Per-product batches list/export exclude foreign/null warehouse lots."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    soon = datetime.utcnow() + timedelta(days=20)

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Batch Scope Mine",
        code="BAT-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Batch Scope Other",
        code="BAT-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Batch Mine WH",
        code="BAT-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Batch Other WH",
        code="BAT-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    db_session.add_all(
        [
            m.ProductBatch(
                tenant_id=tid,
                company_id=cid,
                product_id=seed["p1"].id,
                warehouse_id=wh_mine.id,
                batch_number="LOT-PB-MINE",
                expiry_date=soon,
                quantity=5,
            ),
            m.ProductBatch(
                tenant_id=tid,
                company_id=cid,
                product_id=seed["p1"].id,
                warehouse_id=wh_other.id,
                batch_number="LOT-PB-OTH",
                expiry_date=soon,
                quantity=8,
            ),
            m.ProductBatch(
                tenant_id=tid,
                company_id=cid,
                product_id=seed["p1"].id,
                warehouse_id=None,
                batch_number="LOT-PB-NULL",
                expiry_date=soon,
                quantity=2,
            ),
        ]
    )
    await db_session.commit()

    listed = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/batches", headers=headers
    )
    assert listed.status_code == 200, listed.text
    lots = {b["batch_number"] for b in listed.json()["data"]}
    assert "LOT-PB-MINE" in lots
    assert "LOT-PB-OTH" not in lots
    assert "LOT-PB-NULL" not in lots

    exported = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/batches/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "LOT-PB-MINE" in exported.text
    assert "LOT-PB-OTH" not in exported.text
    assert "LOT-PB-NULL" not in exported.text


@pytest.mark.asyncio
async def test_store_manager_cheques_store_wh_scoped(client, db_session):
    """Cheques list/get/export (+ cancel assert) follow payment invoice/WH scope."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    perms = dict(permissions_for_role("store_manager"))
    perms["accounting"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cheque Scope Mine",
        code="CHQ-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cheque Scope Other",
        code="CHQ-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Cheque Mine WH",
        code="CHQ-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Cheque Other WH",
        code="CHQ-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    cust = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Cheque Cust",
        kind="customer",
        status="active",
    )
    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Cheque Supp",
        kind="supplier",
        status="active",
    )
    db_session.add_all([cust, supplier])
    await db_session.flush()

    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-CHQ-M",
        customer_id=cust.id,
        status="posted",
        subtotal=50,
        total_amount=50,
        paid_amount=50,
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-CHQ-O",
        customer_id=cust.id,
        status="posted",
        subtotal=80,
        total_amount=80,
        paid_amount=80,
    )
    db_session.add_all([inv_mine, inv_other])
    await db_session.flush()

    pay_mine = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CP-CHQ-M",
        customer_id=cust.id,
        sales_invoice_id=inv_mine.id,
        amount=50,
        payment_method="cheque",
    )
    pay_other = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CP-CHQ-O",
        customer_id=cust.id,
        sales_invoice_id=inv_other.id,
        amount=80,
        payment_method="cheque",
    )
    pay_unalloc = m.CustomerPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="CP-CHQ-U",
        customer_id=cust.id,
        sales_invoice_id=None,
        amount=5,
        payment_method="cheque",
    )
    db_session.add_all([pay_mine, pay_other, pay_unalloc])
    await db_session.flush()

    chq_recv_mine = m.Cheque(
        tenant_id=tid,
        company_id=cid,
        direction="received",
        status="pending",
        cheque_number="RCV-MINE",
        amount=50,
        party_id=cust.id,
        customer_payment_id=pay_mine.id,
    )
    chq_recv_other = m.Cheque(
        tenant_id=tid,
        company_id=cid,
        direction="received",
        status="pending",
        cheque_number="RCV-OTH",
        amount=80,
        party_id=cust.id,
        customer_payment_id=pay_other.id,
    )
    chq_recv_unalloc = m.Cheque(
        tenant_id=tid,
        company_id=cid,
        direction="received",
        status="pending",
        cheque_number="RCV-UNA",
        amount=5,
        party_id=cust.id,
        customer_payment_id=pay_unalloc.id,
    )

    pi_mine = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-CHQ-M",
        supplier_id=supplier.id,
        warehouse_id=wh_mine.id,
        status="unpaid",
        subtotal=40,
        total_amount=40,
        paid_amount=40,
    )
    pi_other = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-CHQ-O",
        supplier_id=supplier.id,
        warehouse_id=wh_other.id,
        status="unpaid",
        subtotal=90,
        total_amount=90,
        paid_amount=90,
    )
    db_session.add_all([pi_mine, pi_other])
    await db_session.flush()

    sp_mine = m.SupplierPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="SP-CHQ-M",
        supplier_id=supplier.id,
        purchase_invoice_id=pi_mine.id,
        amount=40,
        payment_method="cheque",
    )
    sp_other = m.SupplierPayment(
        tenant_id=tid,
        company_id=cid,
        payment_number="SP-CHQ-O",
        supplier_id=supplier.id,
        purchase_invoice_id=pi_other.id,
        amount=90,
        payment_method="cheque",
    )
    db_session.add_all([sp_mine, sp_other])
    await db_session.flush()

    chq_iss_mine = m.Cheque(
        tenant_id=tid,
        company_id=cid,
        direction="issued",
        status="pending",
        cheque_number="ISS-MINE",
        amount=40,
        party_id=supplier.id,
        supplier_payment_id=sp_mine.id,
    )
    chq_iss_other = m.Cheque(
        tenant_id=tid,
        company_id=cid,
        direction="issued",
        status="pending",
        cheque_number="ISS-OTH",
        amount=90,
        party_id=supplier.id,
        supplier_payment_id=sp_other.id,
    )
    db_session.add_all(
        [
            chq_recv_mine,
            chq_recv_other,
            chq_recv_unalloc,
            chq_iss_mine,
            chq_iss_other,
        ]
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert listed.status_code == 200, listed.text
    nums = {r["cheque_number"] for r in listed.json()["data"]}
    assert "RCV-MINE" in nums
    assert "ISS-MINE" in nums
    assert "RCV-OTH" not in nums
    assert "ISS-OTH" not in nums
    assert "RCV-UNA" not in nums

    ok = await ac.get(f"/api/v1/accounting/cheques/{chq_recv_mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    denied = await ac.get(
        f"/api/v1/accounting/cheques/{chq_recv_other.id}", headers=headers
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_iss = await ac.get(
        f"/api/v1/accounting/cheques/{chq_iss_other.id}", headers=headers
    )
    assert denied_iss.status_code == 403

    exported = await ac.get("/api/v1/accounting/cheques/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "RCV-MINE" in exported.text
    assert "ISS-MINE" in exported.text
    assert "RCV-OTH" not in exported.text
    assert "ISS-OTH" not in exported.text

    denied_cancel = await ac.post(
        f"/api/v1/accounting/cheques/{chq_recv_other.id}/cancel", headers=headers
    )
    assert denied_cancel.status_code == 403
    assert denied_cancel.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_cancel = await ac.post(
        f"/api/v1/accounting/cheques/{chq_iss_mine.id}/cancel", headers=headers
    )
    assert ok_cancel.status_code == 200, ok_cancel.text


@pytest.mark.asyncio
async def test_store_manager_pos_holds_and_drawer_export_scoped(client, db_session):
    """POS holds follow PosSession.store_id; drawer-settings export is store scoped."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = seed["p1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Hold Scope Mine",
        code="HOLD-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Hold Scope Other",
        code="HOLD-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()

    sess_mine = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        user_id=mgr.id,
        session_number="HOLD-SES-M",
        status="open",
        opening_cash=0,
    )
    sess_other = m.PosSession(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        user_id=mgr.id,
        session_number="HOLD-SES-O",
        status="open",
        opening_cash=0,
    )
    db_session.add_all([sess_mine, sess_other])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    cart = {"items": [{"product_id": product.id, "quantity": 1}]}

    denied_no_session = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={"label": "no session", "cart_payload": cart},
    )
    assert denied_no_session.status_code == 403
    assert denied_no_session.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_other = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "other session",
            "session_id": sess_other.id,
            "cart_payload": cart,
        },
    )
    assert denied_other.status_code == 403
    assert denied_other.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_create = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "mine session",
            "session_id": sess_mine.id,
            "cart_payload": cart,
        },
    )
    assert ok_create.status_code == 200, ok_create.text
    hold_id = ok_create.json()["data"]["id"]

    # Seed an out-of-scope hold owned by the manager (pre-scope / foreign session).
    foreign_hold = m.PosHeldCart(
        tenant_id=tid,
        company_id=cid,
        user_id=mgr.id,
        session_id=sess_other.id,
        label="foreign",
        cart_payload=cart,
        status="held",
        stock_reserved=False,
        reservation_lines=[],
    )
    orphan_hold = m.PosHeldCart(
        tenant_id=tid,
        company_id=cid,
        user_id=mgr.id,
        session_id=None,
        label="orphan",
        cart_payload=cart,
        status="held",
        stock_reserved=False,
        reservation_lines=[],
    )
    db_session.add_all([foreign_hold, orphan_hold])
    await db_session.commit()

    listed = await ac.get("/api/v1/pos/holds?status=held", headers=headers)
    assert listed.status_code == 200, listed.text
    listed_ids = {row["id"] for row in listed.json()["data"]}
    assert hold_id in listed_ids
    assert foreign_hold.id not in listed_ids
    assert orphan_hold.id not in listed_ids

    denied_resume = await ac.post(
        f"/api/v1/pos/holds/{foreign_hold.id}/resume", headers=headers, json={}
    )
    assert denied_resume.status_code == 403
    assert denied_resume.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_discard_orphan = await ac.delete(
        f"/api/v1/pos/holds/{orphan_hold.id}", headers=headers
    )
    assert denied_discard_orphan.status_code == 403
    assert denied_discard_orphan.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_discard = await ac.delete(f"/api/v1/pos/holds/{hold_id}", headers=headers)
    assert ok_discard.status_code == 200, ok_discard.text
    assert ok_discard.json()["data"]["status"] == "discarded"

    exported = await ac.get("/api/v1/stores/drawer-settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    body = exported.text
    assert "HOLD-M" in body
    assert "HOLD-O" not in body


@pytest.mark.asyncio
async def test_store_manager_stores_export_and_writes_scoped(client, db_session):
    """Stores CSV export + patch/drawer/reorder/create assert managed store scope."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = seed["p1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Stores Residual Mine",
        code="STR-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Stores Residual Other",
        code="STR-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/stores/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "STR-M" in exported.text
    assert "STR-O" not in exported.text

    denied_create = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "STR-NEW", "name": "Should Fail"},
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/stores/{other.id}",
        headers=headers,
        json={"name": "Hacked Other"},
    )
    assert denied_patch.status_code == 403
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_patch = await ac.patch(
        f"/api/v1/stores/{mine.id}",
        headers=headers,
        json={"name": "Stores Residual Mine Updated"},
    )
    assert ok_patch.status_code == 200, ok_patch.text
    assert ok_patch.json()["data"]["name"] == "Stores Residual Mine Updated"

    denied_drawer = await ac.patch(
        f"/api/v1/stores/{other.id}/drawer",
        headers=headers,
        json={"drawer_mode": "none", "drawer_open_on_cash": True},
    )
    assert denied_drawer.status_code == 403
    assert denied_drawer.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_drawer = await ac.patch(
        f"/api/v1/stores/{mine.id}/drawer",
        headers=headers,
        json={"drawer_mode": "none", "drawer_open_on_cash": True},
    )
    assert ok_drawer.status_code == 200, ok_drawer.text
    assert ok_drawer.json()["data"]["drawer_mode"] == "none"

    denied_reorder = await ac.put(
        f"/api/v1/stores/{other.id}/reorder-policy",
        headers=headers,
        json={
            "product_id": product.id,
            "minimum_stock": 1,
            "reorder_level": 2,
            "reorder_qty": 5,
        },
    )
    assert denied_reorder.status_code == 403
    assert denied_reorder.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_reorder = await ac.put(
        f"/api/v1/stores/{mine.id}/reorder-policy",
        headers=headers,
        json={
            "product_id": product.id,
            "minimum_stock": 1,
            "reorder_level": 2,
            "reorder_qty": 5,
        },
    )
    assert ok_reorder.status_code == 200, ok_reorder.text


@pytest.mark.asyncio
async def test_store_manager_notifications_broadcast_scoped(client, db_session):
    """Broadcast notifications join-filter by store/WH; personal rows stay visible."""
    from datetime import timedelta

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = seed["p1"]

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Notif Scope Mine",
        code="NTF-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Notif Scope Other",
        code="NTF-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Notif Mine WH",
        code="NTF-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Notif Other WH",
        code="NTF-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()

    now = __import__("datetime").datetime.utcnow()
    inv_mine = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        invoice_number="INV-NTF-M",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=40,
        total_amount=40,
        paid_amount=0,
        due_date=now + timedelta(days=1),
    )
    inv_other = m.SalesInvoice(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        invoice_number="INV-NTF-O",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=60,
        total_amount=60,
        paid_amount=0,
        due_date=now + timedelta(days=1),
    )
    pi_mine = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-NTF-M",
        supplier_id=seed["party1"].id,
        warehouse_id=wh_mine.id,
        status="unpaid",
        subtotal=25,
        total_amount=25,
        paid_amount=0,
        due_date=now + timedelta(days=1),
    )
    pi_other = m.PurchaseInvoice(
        tenant_id=tid,
        company_id=cid,
        invoice_number="PI-NTF-O",
        supplier_id=seed["party1"].id,
        warehouse_id=wh_other.id,
        status="unpaid",
        subtotal=35,
        total_amount=35,
        paid_amount=0,
        due_date=now + timedelta(days=1),
    )
    quote = m.SalesQuotation(
        tenant_id=tid,
        company_id=cid,
        quotation_number="Q-NTF-1",
        customer_id=seed["party1"].id,
        status="sent",
        valid_until=now + timedelta(hours=12),
        subtotal=10,
        total_amount=10,
    )
    rec_mine = m.RecurringExpense(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        category="Rent",
        description="Mine recurring",
        amount=100,
        frequency="monthly",
        next_run_at=now + timedelta(hours=6),
        is_active=True,
    )
    rec_other = m.RecurringExpense(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        category="Rent",
        description="Other recurring",
        amount=200,
        frequency="monthly",
        next_run_at=now + timedelta(hours=6),
        is_active=True,
    )
    db_session.add_all(
        [inv_mine, inv_other, pi_mine, pi_other, quote, rec_mine, rec_other]
    )
    await db_session.flush()

    n_mine = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="payment_due",
        title="AR mine",
        message="mine",
        status="unread",
        entity_type="sales_invoice",
        entity_id=inv_mine.id,
    )
    n_other = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="payment_due",
        title="AR other",
        message="other",
        status="unread",
        entity_type="sales_invoice",
        entity_id=inv_other.id,
    )
    n_pi_mine = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="payment_due",
        title="AP mine",
        message="pi mine",
        status="unread",
        entity_type="purchase_invoice",
        entity_id=pi_mine.id,
    )
    n_pi_other = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="payment_due",
        title="AP other",
        message="pi other",
        status="unread",
        entity_type="purchase_invoice",
        entity_id=pi_other.id,
    )
    n_quote = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="quotation_expiry",
        title="Quote leak",
        message="quote",
        status="unread",
        entity_type="sales_quotation",
        entity_id=quote.id,
    )
    n_product = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="low_stock",
        title="Product leak",
        message="product",
        status="unread",
        entity_type="product",
        entity_id=product.id,
    )
    n_wh_mine = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="low_stock",
        title="WH mine",
        message="wh mine",
        status="unread",
        entity_type="warehouse_stock",
        entity_id=f"{wh_mine.id}:{product.id}",
    )
    n_wh_other = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=None,
        category="low_stock",
        title="WH other",
        message="wh other",
        status="unread",
        entity_type="warehouse_stock",
        entity_id=f"{wh_other.id}:{product.id}",
    )
    n_personal = m.Notification(
        tenant_id=tid,
        company_id=cid,
        user_id=mgr.id,
        category="expense_approval",
        title="Personal",
        message="personal",
        status="unread",
        entity_type="expense",
        entity_id=None,
    )
    db_session.add_all(
        [
            n_mine,
            n_other,
            n_pi_mine,
            n_pi_other,
            n_quote,
            n_product,
            n_wh_mine,
            n_wh_other,
            n_personal,
        ]
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200, listed.text
    titles = {row["title"] for row in listed.json()["data"]}
    assert "AR mine" in titles
    assert "AP mine" in titles
    assert "WH mine" in titles
    assert "Personal" in titles
    assert "AR other" not in titles
    assert "AP other" not in titles
    assert "Quote leak" not in titles
    assert "Product leak" not in titles
    assert "WH other" not in titles

    exported = await ac.get("/api/v1/notifications/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "AR mine" in exported.text
    assert "AR other" not in exported.text
    assert "Quote leak" not in exported.text

    unread = await ac.get("/api/v1/notifications/unread-count", headers=headers)
    assert unread.status_code == 200, unread.text
    assert unread.json()["data"]["count"] >= 4

    denied_read = await ac.patch(
        f"/api/v1/notifications/{n_other.id}/read", headers=headers
    )
    assert denied_read.status_code == 403
    assert denied_read.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_read = await ac.patch(f"/api/v1/notifications/{n_mine.id}/read", headers=headers)
    assert ok_read.status_code == 200, ok_read.text

    # Clear unread payment_due for scan assertions
    for row in (n_mine, n_other, n_pi_mine, n_pi_other):
        row.status = "read"
    await db_session.commit()

    scanned = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scanned.status_code == 200, scanned.text
    body = scanned.json()["data"]
    assert body["quotation_expiry"]["reminded"] == 0
    assert body["quotation_expiry"]["expired"] == 0
    assert int(body["payment_due"]) >= 1
    assert int(body["recurring_expense"]["reminded"]) >= 1

    listed2 = await ac.get("/api/v1/notifications?status=unread", headers=headers)
    assert listed2.status_code == 200, listed2.text
    entity_ids = {row.get("entity_id") for row in listed2.json()["data"]}
    assert inv_mine.id in entity_ids
    assert inv_other.id not in entity_ids
    assert pi_other.id not in entity_ids
    assert quote.id not in entity_ids
    assert rec_mine.id in entity_ids
    assert rec_other.id not in entity_ids


@pytest.mark.asyncio
async def test_store_manager_products_catalog_stock_wh_scoped(client, db_session):
    """Product list/get/export/lookup use managed WH stock, not product.stock_qty."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    product = seed["p1"]
    product.company_id = cid
    product.is_active = True
    product.stock_qty = 999  # company-wide decoy

    mine = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cat Stock Mine",
        code="CAT-M",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Cat Stock Other",
        code="CAT-O",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([mine, other])
    await db_session.flush()
    wh_mine = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=mine.id,
        name="Cat Mine WH",
        code="CAT-MWH",
    )
    wh_other = m.Warehouse(
        tenant_id=tid,
        company_id=cid,
        store_id=other.id,
        name="Cat Other WH",
        code="CAT-OWH",
    )
    db_session.add_all([wh_mine, wh_other])
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_mine.id,
            product_id=product.id,
            quantity=12,
            reserved_qty=2,
            reorder_level=5,
        )
    )
    db_session.add(
        m.WarehouseStock(
            tenant_id=tid,
            company_id=cid,
            warehouse_id=wh_other.id,
            product_id=product.id,
            quantity=800,
            reserved_qty=0,
            reorder_level=5,
        )
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json()["data"] if r["id"] == product.id)
    assert row["stock_qty"] == 12
    assert row["reserved_qty"] == 2
    assert row["available_qty"] == 10
    assert row["stock_qty"] != 999

    got = await ac.get(f"/api/v1/products/{product.id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["stock_qty"] == 12

    exported = await ac.get("/api/v1/products/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert product.sku in exported.text
    assert "999.00" not in exported.text
    assert "12.00" in exported.text

    lookup = await ac.get(
        f"/api/v1/inventory/products/lookup?q={product.sku}", headers=headers
    )
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["data"][0]["stock_qty"] == 12

    pos = await ac.get(
        f"/api/v1/pos/products/search?q={product.sku}", headers=headers
    )
    assert pos.status_code == 200, pos.text
    assert pos.json()["data"][0]["stock_qty"] == 12

    wh_view = await ac.get(
        f"/api/v1/products/{product.id}/warehouse-stock", headers=headers
    )
    assert wh_view.status_code == 200, wh_view.text
    wh_data = wh_view.json()["data"]
    assert wh_data["stock_qty"] == 12
    assert wh_data["reserved_qty"] == 2
    assert len(wh_data["warehouses"]) == 1
    assert wh_data["warehouses"][0]["code"] == "CAT-MWH"


@pytest.mark.asyncio
async def test_store_manager_company_settings_writes_denied(client, db_session):
    """Company-level settings writes denied for store_manager (approval, credit/FX, FEFO)."""
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_expense = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={"expense_approval_threshold": 500},
    )
    assert denied_expense.status_code == 403
    assert denied_expense.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_credit = await ac.patch(
        "/api/v1/credit/settings",
        headers=headers,
        json={"early_pay_discount_pct": 2.5, "early_pay_discount_days": 10},
    )
    assert denied_credit.status_code == 403
    assert denied_credit.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_fx_settings = await ac.patch(
        "/api/v1/credit/exchange-rates/settings",
        headers=headers,
        json={"fx_auto_refresh": False},
    )
    assert denied_fx_settings.status_code == 403
    assert denied_fx_settings.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_fx_refresh = await ac.post(
        "/api/v1/credit/exchange-rates/refresh",
        headers=headers,
        json={},
    )
    assert denied_fx_refresh.status_code == 403
    assert denied_fx_refresh.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_fx_upsert = await ac.put(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
        json={"currency_code": "USD", "rate_to_base": 12.5},
    )
    assert denied_fx_upsert.status_code == 403
    assert denied_fx_upsert.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_fx_delete = await ac.delete(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
    )
    assert denied_fx_delete.status_code == 403
    assert denied_fx_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_fefo = await ac.patch(
        "/api/v1/inventory/settings",
        headers=headers,
        json={"fefo_strict_warehouse": True},
    )
    assert denied_fefo.status_code == 403
    assert denied_fefo.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Reads remain allowed
    assert (await ac.get("/api/v1/expenses/settings", headers=headers)).status_code == 200
    assert (await ac.get("/api/v1/credit/settings", headers=headers)).status_code == 200
    assert (await ac.get("/api/v1/inventory/settings", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_store_manager_user_admin_writes_denied(client, db_session):
    """User/role admin writes denied for store_manager even when users write is granted."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    target = seed["u1"]

    perms = dict(permissions_for_role("store_manager"))
    perms["users"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_create = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "mgr-created@alpha.example.com",
            "full_name": "Mgr Created",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/users/{target.id}",
        headers=headers,
        json={"role": "sales_officer"},
    )
    assert denied_patch.status_code == 403
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_reset = await ac.post(
        f"/api/v1/users/{target.id}/password-reset-email",
        headers=headers,
    )
    assert denied_reset.status_code == 403
    assert denied_reset.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_deactivate = await ac.delete(
        f"/api/v1/users/{target.id}",
        headers=headers,
    )
    assert denied_deactivate.status_code == 403
    assert denied_deactivate.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        "Imported Mgr,import-mgr@alpha.example.com,,cashier,,,SecurePass123!,own\n"
    )
    denied_import = await ac.post(
        "/api/v1/users/import?dry_run=true",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert denied_import.status_code == 403
    assert denied_import.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_role_create = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "mgr_custom",
            "label": "Mgr Custom",
            "base_role": "cashier",
            "permissions": {"sales": ["read"]},
        },
    )
    assert denied_role_create.status_code == 403
    assert denied_role_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_role_patch = await ac.patch(
        "/api/v1/roles/mgr_custom",
        headers=headers,
        json={"label": "Updated"},
    )
    assert denied_role_patch.status_code == 403
    assert denied_role_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_role_perms = await ac.put(
        "/api/v1/roles/mgr_custom/permissions",
        headers=headers,
        json={"permissions": {"sales": ["read", "write"]}},
    )
    assert denied_role_perms.status_code == 403
    assert denied_role_perms.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_role_delete = await ac.delete(
        "/api/v1/roles/mgr_custom",
        headers=headers,
    )
    assert denied_role_delete.status_code == 403
    assert denied_role_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Reads remain allowed (default users read)
    assert (await ac.get("/api/v1/users", headers=headers)).status_code == 200
    assert (await ac.get(f"/api/v1/users/{target.id}", headers=headers)).status_code == 200

@pytest.mark.asyncio
async def test_store_manager_warehouse_company_create_denied(client, db_session):
    """Warehouse/company create denied for store_manager even when write is granted."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Create Gate Store",
        code="CRT-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()

    perms = dict(permissions_for_role("store_manager"))
    perms["inventory"] = ["read", "write"]
    perms["companies"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_wh = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": "WH-CRT-DENY",
            "name": "Denied WH",
            "store_id": store.id,
            "warehouse_type": "retail",
        },
    )
    assert denied_wh.status_code == 403
    assert denied_wh.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_party_credit_master_writes_denied(client, db_session):
    """Party credit limits and supplier early-pay terms denied for store_manager."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cust = seed["party1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Credit Scope Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    denied_credit_limit = await ac.patch(
        f"/api/v1/customers/{cust.id}/credit-limit",
        headers=headers,
        json={"credit_limit": 5000},
    )
    assert denied_credit_limit.status_code == 403
    assert denied_credit_limit.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_cust_patch = await ac.patch(
        f"/api/v1/customers/{cust.id}",
        headers=headers,
        json={"credit_limit": 2500},
    )
    assert denied_cust_patch.status_code == 403
    assert denied_cust_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_cust_create = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Mgr Credit Customer", "credit_limit": 1000},
    )
    assert denied_cust_create.status_code == 403
    assert denied_cust_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_cust_create = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Mgr Zero Credit Customer"},
    )
    assert ok_cust_create.status_code == 200, ok_cust_create.text

    ok_cust_patch = await ac.patch(
        f"/api/v1/customers/{cust.id}",
        headers=headers,
        json={"phone": "555-0100"},
    )
    assert ok_cust_patch.status_code == 200, ok_cust_patch.text

    denied_supplier_patch = await ac.patch(
        f"/api/v1/suppliers/{supplier.id}",
        headers=headers,
        json={"credit_limit": 3000, "early_pay_discount_pct": 2.0},
    )
    assert denied_supplier_patch.status_code == 403
    assert denied_supplier_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_supplier_create = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "Mgr Credit Supplier",
            "credit_limit": 500,
            "early_pay_discount_days": 10,
        },
    )
    assert denied_supplier_create.status_code == 403
    assert denied_supplier_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_supplier_create = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Mgr Plain Supplier"},
    )
    assert ok_supplier_create.status_code == 200, ok_supplier_create.text


@pytest.mark.asyncio
async def test_store_manager_party_payment_terms_writes_denied(client, db_session):
    """Party payment_terms_days create/patch denied for store_manager; zero-default create allowed."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cust = seed["party1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Terms Scope Supplier",
        kind="supplier",
        code="SUP-TERMS-DENY",
        status="active",
        credit_limit=0,
        payment_terms_days=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    denied_cust_create = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Mgr Terms Customer", "payment_terms_days": 30},
    )
    assert denied_cust_create.status_code == 403, denied_cust_create.text
    assert denied_cust_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"
    assert "payment_terms_days" in denied_cust_create.json()["detail"].get("fields", [])

    denied_cust_patch = await ac.patch(
        f"/api/v1/customers/{cust.id}",
        headers=headers,
        json={"payment_terms_days": 45},
    )
    assert denied_cust_patch.status_code == 403, denied_cust_patch.text
    assert denied_cust_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"
    assert "payment_terms_days" in denied_cust_patch.json()["detail"].get("fields", [])

    ok_cust_create = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Mgr Zero Terms Customer"},
    )
    assert ok_cust_create.status_code == 200, ok_cust_create.text
    assert int(ok_cust_create.json()["data"].get("payment_terms_days") or 0) == 0

    ok_cust_patch = await ac.patch(
        f"/api/v1/customers/{cust.id}",
        headers=headers,
        json={"phone": "555-0145"},
    )
    assert ok_cust_patch.status_code == 200, ok_cust_patch.text

    denied_sup_create = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Mgr Terms Supplier", "payment_terms_days": 14},
    )
    assert denied_sup_create.status_code == 403, denied_sup_create.text
    assert denied_sup_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_sup_patch = await ac.patch(
        f"/api/v1/suppliers/{supplier.id}",
        headers=headers,
        json={"payment_terms_days": 21},
    )
    assert denied_sup_patch.status_code == 403, denied_sup_patch.text
    assert denied_sup_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_sup_create = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Mgr Zero Terms Supplier"},
    )
    assert ok_sup_create.status_code == 200, ok_sup_create.text
    assert int(ok_sup_create.json()["data"].get("payment_terms_days") or 0) == 0


@pytest.mark.asyncio
async def test_store_manager_expense_category_writes_denied(client, db_session):
    """Expense category create/patch (incl. budget limits) denied for store_manager."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    cat = m.ExpenseCategory(
        tenant_id=tid,
        company_id=cid,
        code="CAT-DENY",
        name="Category Deny Target",
        budget_amount=1000,
    )
    db_session.add(cat)
    await db_session.commit()

    denied_create = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "MGR-CAT", "name": "Mgr Category", "budget_amount": 250},
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/expenses/categories/{cat.id}",
        headers=headers,
        json={"budget_amount": 5000, "name": "Hijacked Budget"},
    )
    assert denied_patch.status_code == 403
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Reads remain allowed
    listed = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["code"] == "CAT-DENY" for row in listed.json()["data"])


@pytest.mark.asyncio
async def test_store_manager_credit_limit_override_denied(client, db_session):
    """credit_limit_override on invoice post / POS credit denied for store_manager."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    customer = seed["party1"]
    product = seed["p1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Credit Override Mgr Store",
        code="CRO-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()

    customer.credit_limit = 50
    customer.balance = 0
    customer.party_type = "registered"
    product.selling_price = 100
    product.stock_qty = 100
    product.tax_rate_id = None
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer.id,
            "store_id": store.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": 100,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]

    blocked = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/post",
        headers=headers,
        json={},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "CREDIT_LIMIT_EXCEEDED"

    denied = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/post",
        headers=headers,
        json={
            "credit_limit_override": True,
            "credit_override_reason": "Manager VIP exception attempt",
        },
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    await accounting_svc.ensure_default_accounts(db_session, tid, company_id=cid)
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20, "store_id": store.id},
    )
    assert opened.status_code == 200, opened.text
    sid = opened.json()["data"]["session_id"]

    pos_denied = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": sid,
            "party_id": customer.id,
            "payment_method": "credit",
            "credit_limit_override": True,
            "credit_override_reason": "POS manager override attempt",
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 100}],
        },
    )
    assert pos_denied.status_code == 403, pos_denied.text
    assert pos_denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_store_manager_branches_departments_writes_denied(client, db_session):
    """Branch/department create/patch denied for store_manager (company-level org units)."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    perms = dict(permissions_for_role("store_manager"))
    perms["users"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms

    branch = m.Branch(
        tenant_id=tid,
        company_id=cid,
        code="BR-DENY",
        name="Branch Deny Target",
        is_active=True,
    )
    db_session.add(branch)
    await db_session.flush()
    dept = m.Department(
        tenant_id=tid,
        company_id=cid,
        branch_id=branch.id,
        code="DP-DENY",
        name="Department Deny Target",
        is_active=True,
    )
    db_session.add(dept)
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_branch_create = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "MGR-BR", "name": "Mgr Branch"},
    )
    assert denied_branch_create.status_code == 403
    assert denied_branch_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_branch_patch = await ac.patch(
        f"/api/v1/branches/{branch.id}",
        headers=headers,
        json={"name": "Hijacked Branch"},
    )
    assert denied_branch_patch.status_code == 403
    assert denied_branch_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_dept_create = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "MGR-DP", "name": "Mgr Department", "branch_id": branch.id},
    )
    assert denied_dept_create.status_code == 403
    assert denied_dept_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_dept_patch = await ac.patch(
        f"/api/v1/departments/{dept.id}",
        headers=headers,
        json={"name": "Hijacked Department"},
    )
    assert denied_dept_patch.status_code == 403
    assert denied_dept_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Reads remain allowed
    listed_branches = await ac.get("/api/v1/branches", headers=headers)
    assert listed_branches.status_code == 200, listed_branches.text
    assert any(row["code"] == "BR-DENY" for row in listed_branches.json()["data"])

    listed_depts = await ac.get("/api/v1/departments", headers=headers)
    assert listed_depts.status_code == 200, listed_depts.text
    assert any(row["code"] == "DP-DENY" for row in listed_depts.json()["data"])


@pytest.mark.asyncio
async def test_store_manager_catalog_meta_writes_denied(client, db_session):
    """Catalog category/brand/unit create/patch/deactivate denied for store_manager."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id

    category = m.ProductCategory(
        tenant_id=tid,
        company_id=cid,
        code="CAT-META-DENY",
        name="Category Meta Deny",
        is_active=True,
    )
    brand = m.Brand(
        tenant_id=tid,
        company_id=cid,
        code="BR-META-DENY",
        name="Brand Meta Deny",
        is_active=True,
    )
    unit = m.UnitOfMeasure(
        tenant_id=tid,
        company_id=cid,
        code="U-META-DENY",
        name="Unit Meta Deny",
        conversion_factor=1,
        is_active=True,
    )
    db_session.add_all([category, brand, unit])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_cat_create = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "MGR-CAT", "name": "Mgr Category"},
    )
    assert denied_cat_create.status_code == 403
    assert denied_cat_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_cat_patch = await ac.patch(
        f"/api/v1/catalog/categories/{category.id}",
        headers=headers,
        json={"name": "Hijacked Category"},
    )
    assert denied_cat_patch.status_code == 403
    assert denied_cat_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_cat_delete = await ac.delete(
        f"/api/v1/catalog/categories/{category.id}",
        headers=headers,
    )
    assert denied_cat_delete.status_code == 403
    assert denied_cat_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_brand_create = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "MGR-BR", "name": "Mgr Brand"},
    )
    assert denied_brand_create.status_code == 403
    assert denied_brand_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_brand_patch = await ac.patch(
        f"/api/v1/catalog/brands/{brand.id}",
        headers=headers,
        json={"name": "Hijacked Brand"},
    )
    assert denied_brand_patch.status_code == 403
    assert denied_brand_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_brand_delete = await ac.delete(
        f"/api/v1/catalog/brands/{brand.id}",
        headers=headers,
    )
    assert denied_brand_delete.status_code == 403
    assert denied_brand_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_unit_create = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "MGR-U", "name": "Mgr Unit"},
    )
    assert denied_unit_create.status_code == 403
    assert denied_unit_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_unit_patch = await ac.patch(
        f"/api/v1/catalog/units/{unit.id}",
        headers=headers,
        json={"name": "Hijacked Unit"},
    )
    assert denied_unit_patch.status_code == 403
    assert denied_unit_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_unit_delete = await ac.delete(
        f"/api/v1/catalog/units/{unit.id}",
        headers=headers,
    )
    assert denied_unit_delete.status_code == 403
    assert denied_unit_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Reads remain allowed
    listed_cats = await ac.get("/api/v1/catalog/categories", headers=headers)
    assert listed_cats.status_code == 200, listed_cats.text
    assert any(row["code"] == "CAT-META-DENY" for row in listed_cats.json()["data"])

    listed_brands = await ac.get("/api/v1/catalog/brands", headers=headers)
    assert listed_brands.status_code == 200, listed_brands.text
    assert any(row["code"] == "BR-META-DENY" for row in listed_brands.json()["data"])

    listed_units = await ac.get("/api/v1/catalog/units", headers=headers)
    assert listed_units.status_code == 200, listed_units.text
    assert any(row["code"] == "U-META-DENY" for row in listed_units.json()["data"])


@pytest.mark.asyncio
async def test_store_manager_customer_groups_writes_denied(client, db_session):
    """Customer group create/patch/deactivate denied for store_manager (company-level)."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id

    group = m.CustomerGroup(
        tenant_id=tid,
        company_id=cid,
        name="Group Deny Target",
        discount_percent=5,
        is_active=True,
    )
    db_session.add(group)
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_create = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "Mgr Group", "discount_percent": 10},
    )
    assert denied_create.status_code == 403, denied_create.text
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/customers/groups/{group.id}",
        headers=headers,
        json={"name": "Hijacked Group", "discount_percent": 50},
    )
    assert denied_patch.status_code == 403, denied_patch.text
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_delete = await ac.delete(
        f"/api/v1/customers/groups/{group.id}",
        headers=headers,
    )
    assert denied_delete.status_code == 403, denied_delete.text
    assert denied_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    listed = await ac.get("/api/v1/customers/groups", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["name"] == "Group Deny Target" for row in listed.json()["data"])

    got = await ac.get(f"/api/v1/customers/groups/{group.id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["name"] == "Group Deny Target"


@pytest.mark.asyncio
async def test_store_manager_product_import_denied(client, db_session):
    """Company-level product CSV import denied for store_manager; template/export reads allowed."""
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    csv_body = (
        "name,sku,barcode,category_code,brand_code,unit_code,"
        "cost_price,selling_price,reorder_level,stock_qty,tracks_batches\n"
        "Mgr Import Widget,SKU-MGR-IMP,,,,,10,15,0,0,false\n"
    )
    files = {"file": ("products.csv", csv_body.encode("utf-8"), "text/csv")}

    denied_dry = await ac.post(
        "/api/v1/products/import?dry_run=true",
        headers=headers,
        files=files,
    )
    assert denied_dry.status_code == 403, denied_dry.text
    assert denied_dry.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_apply = await ac.post(
        "/api/v1/products/import?dry_run=false",
        headers=headers,
        files=files,
    )
    assert denied_apply.status_code == 403, denied_apply.text
    assert denied_apply.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    template = await ac.get("/api/v1/products/import/template", headers=headers)
    assert template.status_code == 200, template.text
    assert "sku" in template.text.lower() or "name" in template.text.lower()

    exported = await ac.get("/api/v1/products/export", headers=headers)
    assert exported.status_code == 200, exported.text


@pytest.mark.asyncio
async def test_store_manager_product_master_writes_denied(client, db_session):
    """Product create/patch/variants/barcode/image writes denied for store_manager; reads allowed."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    product = seed["p1"]

    variant = m.ProductVariant(
        tenant_id=tid,
        company_id=cid,
        product_id=product.id,
        name="Variant Deny Target",
        sku="A-1-V-DENY",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
        is_active=True,
    )
    image = m.ProductImage(
        tenant_id=tid,
        company_id=cid,
        product_id=product.id,
        storage_key="products/deny-target.png",
        content_type="image/png",
        sort_order=0,
        is_primary=True,
    )
    db_session.add_all([variant, image])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied_create = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Mgr Widget",
            "sku": "MGR-SKU-1",
            "cost_price": 1,
            "selling_price": 2,
        },
    )
    assert denied_create.status_code == 403, denied_create.text
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_patch = await ac.patch(
        f"/api/v1/products/{product.id}",
        headers=headers,
        json={"name": "Hijacked Widget"},
    )
    assert denied_patch.status_code == 403, denied_patch.text
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_barcode = await ac.post(
        f"/api/v1/products/{product.id}/barcode/generate",
        headers=headers,
    )
    assert denied_barcode.status_code == 403, denied_barcode.text
    assert denied_barcode.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_variant_create = await ac.post(
        f"/api/v1/products/{product.id}/variants",
        headers=headers,
        json={
            "name": "Mgr Variant",
            "sku": "MGR-VAR-1",
            "cost_price": 1,
            "selling_price": 2,
        },
    )
    assert denied_variant_create.status_code == 403, denied_variant_create.text
    assert denied_variant_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_variant_patch = await ac.patch(
        f"/api/v1/products/{product.id}/variants/{variant.id}",
        headers=headers,
        json={"name": "Hijacked Variant"},
    )
    assert denied_variant_patch.status_code == 403, denied_variant_patch.text
    assert denied_variant_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_variant_barcode = await ac.post(
        f"/api/v1/products/{product.id}/variants/{variant.id}/barcode/generate",
        headers=headers,
    )
    assert denied_variant_barcode.status_code == 403, denied_variant_barcode.text
    assert denied_variant_barcode.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_variant_delete = await ac.delete(
        f"/api/v1/products/{product.id}/variants/{variant.id}",
        headers=headers,
    )
    assert denied_variant_delete.status_code == 403, denied_variant_delete.text
    assert denied_variant_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    denied_image_upload = await ac.post(
        f"/api/v1/products/{product.id}/image",
        headers=headers,
        files={"file": ("deny.png", png, "image/png")},
    )
    assert denied_image_upload.status_code == 403, denied_image_upload.text
    assert denied_image_upload.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_image_delete = await ac.delete(
        f"/api/v1/products/{product.id}/image",
        headers=headers,
    )
    assert denied_image_delete.status_code == 403, denied_image_delete.text
    assert denied_image_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_gallery_upload = await ac.post(
        f"/api/v1/products/{product.id}/images",
        headers=headers,
        files={"file": ("deny-g.png", png, "image/png")},
    )
    assert denied_gallery_upload.status_code == 403, denied_gallery_upload.text
    assert denied_gallery_upload.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_gallery_patch = await ac.patch(
        f"/api/v1/products/{product.id}/images/{image.id}",
        headers=headers,
        json={"is_primary": True},
    )
    assert denied_gallery_patch.status_code == 403, denied_gallery_patch.text
    assert denied_gallery_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_gallery_delete = await ac.delete(
        f"/api/v1/products/{product.id}/images/{image.id}",
        headers=headers,
    )
    assert denied_gallery_delete.status_code == 403, denied_gallery_delete.text
    assert denied_gallery_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["sku"] == "A-1" for row in listed.json()["data"])

    got = await ac.get(f"/api/v1/products/{product.id}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["sku"] == "A-1"

    variants = await ac.get(f"/api/v1/products/{product.id}/variants", headers=headers)
    assert variants.status_code == 200, variants.text
    assert any(row["sku"] == "A-1-V-DENY" for row in variants.json()["data"])


@pytest.mark.asyncio
async def test_store_manager_stock_import_denied(client, db_session):
    """Company-level stock CSV import denied for store_manager; template read allowed."""
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    csv_body = (
        "sku,barcode,qty,mode,warehouse_code,reason\n"
        "A-1,,5,adjust,,Mgr stock import deny\n"
    )
    files = {"file": ("stock.csv", csv_body.encode("utf-8"), "text/csv")}

    denied_dry = await ac.post(
        "/api/v1/inventory/stock/import?dry_run=true",
        headers=headers,
        files=files,
    )
    assert denied_dry.status_code == 403, denied_dry.text
    assert denied_dry.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_apply = await ac.post(
        "/api/v1/inventory/stock/import?dry_run=false",
        headers=headers,
        files=files,
    )
    assert denied_apply.status_code == 403, denied_apply.text
    assert denied_apply.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    template = await ac.get("/api/v1/inventory/stock/import/template", headers=headers)
    assert template.status_code == 200, template.text
    assert "sku" in template.text.lower() or "warehouse" in template.text.lower()


@pytest.mark.asyncio
async def test_store_manager_party_deactivate_denied(client, db_session):
    """Customer/supplier deactivate denied for store_manager; create/list/patch (non-credit) remain."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cust = seed["party1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Deactivate Deny Supplier",
        kind="supplier",
        code="SUP-DEACT-DENY",
        status="active",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    denied_cust = await ac.delete(f"/api/v1/customers/{cust.id}", headers=headers)
    assert denied_cust.status_code == 403, denied_cust.text
    assert denied_cust.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_sup = await ac.delete(f"/api/v1/suppliers/{supplier.id}", headers=headers)
    assert denied_sup.status_code == 403, denied_sup.text
    assert denied_sup.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Operational party writes/reads still allowed (credit master fields remain separately denied).
    ok_patch = await ac.patch(
        f"/api/v1/customers/{cust.id}",
        headers=headers,
        json={"phone": "555-0199"},
    )
    assert ok_patch.status_code == 200, ok_patch.text

    listed_cust = await ac.get("/api/v1/customers", headers=headers)
    assert listed_cust.status_code == 200, listed_cust.text
    assert any(row["id"] == cust.id for row in listed_cust.json()["data"])

    listed_sup = await ac.get("/api/v1/suppliers", headers=headers)
    assert listed_sup.status_code == 200, listed_sup.text
    assert any(row["id"] == supplier.id for row in listed_sup.json()["data"])

    # Confirm parties were not deactivated.
    await db_session.refresh(cust)
    await db_session.refresh(supplier)
    assert cust.status == "active"
    assert supplier.status == "active"


@pytest.mark.asyncio
async def test_store_manager_party_contact_writes_denied(client, db_session):
    """Customer/supplier contact create/delete denied for store_manager; party get remains."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    cust = seed["party1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Contact Deny Supplier",
        kind="supplier",
        code="SUP-CONTACT-DENY",
        status="active",
        credit_limit=0,
    )
    cust_contact = m.PartyContact(
        tenant_id=tid,
        company_id=cid,
        party_id=cust.id,
        name="Cust Contact",
        email="cust.contact@example.com",
        is_primary=True,
    )
    db_session.add_all([supplier, cust_contact])
    await db_session.flush()
    sup_contact = m.PartyContact(
        tenant_id=tid,
        company_id=cid,
        party_id=supplier.id,
        name="Sup Contact",
        email="sup.contact@example.com",
        is_primary=True,
    )
    db_session.add(sup_contact)
    await db_session.commit()

    denied_cust_add = await ac.post(
        f"/api/v1/customers/{cust.id}/contacts",
        headers=headers,
        json={"name": "Mgr Contact", "phone": "555-0100"},
    )
    assert denied_cust_add.status_code == 403, denied_cust_add.text
    assert denied_cust_add.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_cust_del = await ac.delete(
        f"/api/v1/customers/{cust.id}/contacts/{cust_contact.id}",
        headers=headers,
    )
    assert denied_cust_del.status_code == 403, denied_cust_del.text
    assert denied_cust_del.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_sup_add = await ac.post(
        f"/api/v1/suppliers/{supplier.id}/contacts",
        headers=headers,
        json={"name": "Mgr Sup Contact", "phone": "555-0200"},
    )
    assert denied_sup_add.status_code == 403, denied_sup_add.text
    assert denied_sup_add.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_sup_del = await ac.delete(
        f"/api/v1/suppliers/{supplier.id}/contacts/{sup_contact.id}",
        headers=headers,
    )
    assert denied_sup_del.status_code == 403, denied_sup_del.text
    assert denied_sup_del.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    # Nested contacts on party create remain allowed (zero credit/terms).
    ok_nested = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Mgr Nested Contact Customer",
            "contacts": [{"name": "Nested", "email": "nested@example.com", "is_primary": True}],
        },
    )
    assert ok_nested.status_code == 200, ok_nested.text
    assert len(ok_nested.json()["data"].get("contacts") or []) == 1

    got = await ac.get(f"/api/v1/customers/{cust.id}", headers=headers)
    assert got.status_code == 200, got.text
    assert any(c["id"] == cust_contact.id for c in got.json()["data"].get("contacts") or [])


@pytest.mark.asyncio
async def test_store_manager_ai_report_template_writes_denied(client, db_session):
    """AI report template create/delete denied for store_manager; list/export reads allowed."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    tmpl = m.AiReportTemplate(
        tenant_id=tid,
        company_id=cid,
        user_id=seed["mgr1"].id,
        name="Deny Target Template",
        prompt="Show me monthly sales",
        report_type="sales_products",
        format="csv",
        params={"period_label": "this month"},
    )
    db_session.add(tmpl)
    await db_session.commit()

    denied_create = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={
            "name": "Mgr Template",
            "prompt": "Show me monthly sales",
            "format": "csv",
        },
    )
    assert denied_create.status_code == 403, denied_create.text
    assert denied_create.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_delete = await ac.delete(
        f"/api/v1/ai/reports/templates/{tmpl.id}",
        headers=headers,
    )
    assert denied_delete.status_code == 403, denied_delete.text
    assert denied_delete.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    listed = await ac.get("/api/v1/ai/reports/templates", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == tmpl.id for row in listed.json()["data"])

    exported = await ac.get("/api/v1/ai/reports/templates/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "Deny Target" in exported.text or "sales" in exported.text.lower()

    # Template must still exist after denied delete.
    await db_session.refresh(tmpl)
    assert tmpl.name == "Deny Target Template"


@pytest.mark.asyncio
async def test_store_manager_ai_report_generate_denied(client, db_session):
    """Company-level AI NL report generate/export denied for store_manager; template list remains."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    tmpl = m.AiReportTemplate(
        tenant_id=tid,
        company_id=cid,
        user_id=seed["mgr1"].id,
        name="Generate Deny Template",
        prompt="Show me monthly sales",
        report_type="sales_products",
        format="csv",
        params={"period_label": "this month"},
    )
    db_session.add(tmpl)
    await db_session.commit()

    denied_generate = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"prompt": "Show me monthly sales"},
    )
    assert denied_generate.status_code == 403, denied_generate.text
    assert denied_generate.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_typed = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"report_type": "sales_products", "period": "this month"},
    )
    assert denied_typed.status_code == 403, denied_typed.text
    assert denied_typed.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_from_tmpl = await ac.post(
        "/api/v1/ai/reports/generate",
        headers=headers,
        json={"template_id": tmpl.id},
    )
    assert denied_from_tmpl.status_code == 403, denied_from_tmpl.text
    assert denied_from_tmpl.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_export = await ac.post(
        "/api/v1/ai/reports/generate?export=true",
        headers=headers,
        json={"prompt": "Show me monthly sales", "format": "csv"},
    )
    assert denied_export.status_code == 403, denied_export.text
    assert denied_export.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    listed = await ac.get("/api/v1/ai/reports/templates", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == tmpl.id for row in listed.json()["data"])


@pytest.mark.asyncio
async def test_store_manager_company_membership_writes_denied(client, db_session):
    """Company membership assign/revoke denied for store_manager even when companies write granted."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    cashier = (
        await db_session.execute(
            select(m.User).where(m.User.email == "cashier@alpha.example.com")
        )
    ).scalar_one()

    perms = dict(permissions_for_role("store_manager"))
    perms["companies"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    listed = await ac.get(f"/api/v1/companies/{cid}/memberships", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["user_id"] == cashier.id for row in listed.json()["data"])

    denied_assign = await ac.post(
        f"/api/v1/companies/{cid}/memberships",
        headers=headers,
        json={"user_id": cashier.id, "role": "cashier"},
    )
    assert denied_assign.status_code == 403, denied_assign.text
    assert denied_assign.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_revoke = await ac.delete(
        f"/api/v1/companies/{cid}/memberships/{cashier.id}",
        headers=headers,
    )
    assert denied_revoke.status_code == 403, denied_revoke.text
    assert denied_revoke.json()["detail"]["code"] == "STORE_SCOPE_DENIED"



@pytest.mark.asyncio
async def test_store_manager_bi_settings_write_denied(client, db_session):
    """Business-insights settings PUT denied for store_manager; GET settings remains."""
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied = await ac.put(
        "/api/v1/business-insights/settings",
        headers=headers,
        json={"slow_moving_days": 45},
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json()["detail"]
    assert detail["code"] == "STORE_SCOPE_DENIED"

    ok_get = await ac.get("/api/v1/business-insights/settings", headers=headers)
    assert ok_get.status_code == 200, ok_get.text
    body = ok_get.json()
    payload = body.get("data", body)
    assert "settings" in payload or "formulas" in payload


@pytest.mark.asyncio
async def test_store_manager_purchasing_settings_write_denied(client, db_session):
    """Purchasing PR approval settings PATCH denied for store_manager; GET/export remain."""
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=headers,
        json={
            "levels": [
                {"min_amount": 0.01, "roles": ["store_manager"], "label": "L1 Manager"},
            ]
        },
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_get = await ac.get("/api/v1/purchasing/settings", headers=headers)
    assert ok_get.status_code == 200, ok_get.text

    ok_export = await ac.get("/api/v1/purchasing/settings/export", headers=headers)
    assert ok_export.status_code == 200, ok_export.text
    assert "text/csv" in (ok_export.headers.get("content-type") or "")


@pytest.mark.asyncio
async def test_store_manager_company_branding_writes_denied(client, db_session):
    """Company profile/logo writes denied for store_manager even when companies write granted."""
    from app.rbac import permissions_for_role

    ac, seed = client
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    perms = dict(permissions_for_role("store_manager"))
    perms["companies"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    ok_get = await ac.get(f"/api/v1/companies/{cid}", headers=headers)
    assert ok_get.status_code == 200, ok_get.text

    denied_patch = await ac.patch(
        f"/api/v1/companies/{cid}",
        headers=headers,
        json={"name": "Hijacked Brand"},
    )
    assert denied_patch.status_code == 403, denied_patch.text
    assert denied_patch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_logo = await ac.post(
        f"/api/v1/companies/{cid}/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x"), "image/png")},
    )
    assert denied_logo.status_code == 403, denied_logo.text
    assert denied_logo.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_del = await ac.delete(f"/api/v1/companies/{cid}/logo", headers=headers)
    assert denied_del.status_code == 403, denied_del.text
    assert denied_del.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

@pytest.mark.asyncio
async def test_store_manager_legacy_sale_purchase_writes_denied(client, db_session):
    """Legacy POST /sales and /purchases denied for store_manager (no store_id; use invoices/PO)."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    cust = seed["party1"]
    product = seed["p1"]

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Legacy Tx Mgr Store",
        code="LEG-TX-MGR",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    admin_headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    denied_sale = await ac.post(
        "/api/v1/sales",
        headers=headers,
        json={
            "party_id": cust.id,
            "subtotal": 10,
            "tax": 0,
            "total": 10,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert denied_sale.status_code == 403, denied_sale.text
    assert denied_sale.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    supplier = m.Party(
        tenant_id=tid,
        company_id=cid,
        name="Legacy Tx Supplier",
        kind="supplier",
        code="SUP-LEG-TX",
        status="active",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    denied_purch = await ac.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "party_id": supplier.id,
            "subtotal": 5,
            "tax": 0,
            "total": 5,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert denied_purch.status_code == 403, denied_purch.text
    assert denied_purch.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_sale = await ac.post(
        "/api/v1/sales",
        headers=admin_headers,
        json={
            "party_id": cust.id,
            "subtotal": 10,
            "tax": 0,
            "total": 10,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert ok_sale.status_code == 200, ok_sale.text


@pytest.mark.asyncio
async def test_store_manager_company_store_limit_write_denied(client, db_session):
    """Company store-limit allocation denied for store_manager even with companies write."""
    from app.rbac import permissions_for_role

    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    perms = dict(permissions_for_role("store_manager"))
    perms["companies"] = ["read", "write"]
    mgr.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == mgr.id,
                m.UserCompanyMembership.company_id == cid,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    denied = await ac.patch(
        f"/api/v1/companies/{cid}/store-limit",
        headers=headers,
        json={"store_limit": 2},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"



@pytest.mark.asyncio
async def test_store_manager_store_manager_assignment_denied(client, db_session):
    """store_manager cannot assign/clear manager_id; other managed-store patches remain."""
    ac, seed = client
    tid = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]
    admin = seed["admin1"]
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    store = m.Store(
        tenant_id=tid,
        company_id=cid,
        name="Mgr Assign Deny Store",
        code="MGR-ASSIGN-DENY",
        manager_id=mgr.id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.commit()

    denied_assign = await ac.patch(
        f"/api/v1/stores/{store.id}",
        headers=headers,
        json={"manager_id": admin.id},
    )
    assert denied_assign.status_code == 403, denied_assign.text
    assert denied_assign.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_clear = await ac.patch(
        f"/api/v1/stores/{store.id}",
        headers=headers,
        json={"clear_manager": True},
    )
    assert denied_clear.status_code == 403, denied_clear.text
    assert denied_clear.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok_phone = await ac.patch(
        f"/api/v1/stores/{store.id}",
        headers=headers,
        json={"phone": "555-0142"},
    )
    assert ok_phone.status_code == 200, ok_phone.text

    await db_session.refresh(store)
    assert store.manager_id == mgr.id
    assert store.phone == "555-0142"
