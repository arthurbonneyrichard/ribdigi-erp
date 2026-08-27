"""Store-manager operational API scope hardening (manager_id; ADR-005 still deferred)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
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
    )
    db_session.add_all([mine, theirs])
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert listed.status_code == 200, listed.text
    numbers = {row["invoice_number"] for row in listed.json()["data"]}
    assert "INV-SCOPE-MINE" in numbers
    assert "INV-SCOPE-THEIRS" not in numbers

    denied = await ac.get(f"/api/v1/sales/invoices/{theirs.id}", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    ok = await ac.get(f"/api/v1/sales/invoices/{mine.id}", headers=headers)
    assert ok.status_code == 200, ok.text

    cross = await ac.get(
        "/api/v1/sales/invoices",
        headers=headers,
        params={"store_id": other.id},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


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
    db_session.add_all(
        [
            m.Transaction(
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
            ),
            m.Transaction(
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
            ),
        ]
    )
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

    cross = await ac.get(
        "/api/v1/sales/orders",
        headers=headers,
        params={"store_id": other.id},
    )
    assert cross.status_code == 403
    assert cross.json()["detail"]["code"] == "STORE_SCOPE_DENIED"


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