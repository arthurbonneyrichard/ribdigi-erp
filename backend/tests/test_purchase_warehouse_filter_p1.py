"""Purchase report warehouse/store filters (BR-14.3 / BR-14.5)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_purchase_reports_filter_by_warehouse_and_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    supplier = m.Party(
        tenant_id=tenant_id,
        kind="supplier",
        name="PO Filter Supplier",
        email="po-filter@example.com",
    )
    db_session.add(supplier)
    await db_session.flush()

    store_a = m.Store(tenant_id=tenant_id, code="PO-A", name="PO Store A")
    store_b = m.Store(tenant_id=tenant_id, code="PO-B", name="PO Store B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    wh_a = m.Warehouse(
        tenant_id=tenant_id, code="WH-PO-A", name="WH A", store_id=store_a.id
    )
    wh_b = m.Warehouse(
        tenant_id=tenant_id, code="WH-PO-B", name="WH B", store_id=store_b.id
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    now = datetime.utcnow()
    po_a = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-FILT-A1",
        supplier_id=supplier.id,
        warehouse_id=wh_a.id,
        status="sent",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        created_at=now,
    )
    po_b = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-FILT-B1",
        supplier_id=supplier.id,
        warehouse_id=wh_b.id,
        status="sent",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        paid_amount=0,
        created_at=now,
    )
    po_unscoped = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-FILT-U1",
        supplier_id=supplier.id,
        warehouse_id=None,
        status="draft",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        paid_amount=0,
        created_at=now,
    )
    db_session.add_all([po_a, po_b, po_unscoped])
    await db_session.commit()

    all_r = await ac.get("/api/v1/reports/purchases/summary", headers=headers)
    assert all_r.status_code == 200, all_r.text
    assert all_r.json()["data"]["total_amount"] >= 150

    by_wh = await ac.get(
        f"/api/v1/reports/purchases/summary?warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert by_wh.status_code == 200, by_wh.text
    wdata = by_wh.json()["data"]
    assert wdata["warehouse_id"] == wh_a.id
    assert wdata["warehouse_name"] == "WH A"
    assert wdata["store_id"] == store_a.id
    assert wdata["total_amount"] == 100.0
    assert wdata["order_count"] == 1

    by_store = await ac.get(
        f"/api/v1/reports/purchases/summary?store_id={store_a.id}",
        headers=headers,
    )
    assert by_store.status_code == 200, by_store.text
    sdata = by_store.json()["data"]
    assert sdata["store_id"] == store_a.id
    assert sdata["store_name"] == "PO Store A"
    assert sdata["total_amount"] == 100.0

    pending = await ac.get(
        f"/api/v1/reports/purchases/pending-orders?store_id={store_b.id}",
        headers=headers,
    )
    assert pending.status_code == 200, pending.text
    pdata = pending.json()["data"]
    assert pdata["store_id"] == store_b.id
    assert pdata["order_count"] == 1
    assert pdata["orders"][0]["po_number"] == "PO-FILT-B1"

    suppliers = await ac.get(
        f"/api/v1/reports/purchases/suppliers?warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert suppliers.status_code == 200, suppliers.text
    assert suppliers.json()["data"]["total_amount"] == 100.0

    mismatch = await ac.get(
        f"/api/v1/reports/purchases/summary?store_id={store_b.id}&warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert mismatch.status_code == 400

    missing = await ac.get(
        "/api/v1/reports/purchases/summary?warehouse_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
