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
