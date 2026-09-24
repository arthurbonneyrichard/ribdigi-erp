"""Purchase returns report warehouse/store filters (BR-14.3 / BR-14.5)."""

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
async def test_purchase_returns_filter_by_warehouse_and_store(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    supplier = m.Party(
        tenant_id=tenant_id,
        kind="supplier",
        name="PR Location Supplier",
        email="pr-loc@example.com",
    )
    db_session.add(supplier)
    await db_session.flush()

    store_a = m.Store(tenant_id=tenant_id, code="PR-A", name="PR Store A")
    store_b = m.Store(tenant_id=tenant_id, code="PR-B", name="PR Store B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    wh_a = m.Warehouse(
        tenant_id=tenant_id, code="WH-PR-A", name="WH PR A", store_id=store_a.id
    )
    wh_b = m.Warehouse(
        tenant_id=tenant_id, code="WH-PR-B", name="WH PR B", store_id=store_b.id
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-PR-LOC-1",
        supplier_id=supplier.id,
        warehouse_id=wh_a.id,
        status="received",
        total_amount=100,
    )
    db_session.add(po)
    await db_session.flush()
    po_item = m.PurchaseOrderItem(
        tenant_id=tenant_id,
        purchase_order_id=po.id,
        product_id=product.id,
        quantity=10,
        received_qty=10,
        unit_price=10,
        tax_rate=0,
        line_total=100,
    )
    db_session.add(po_item)
    await db_session.flush()

    grn = m.GoodsReceipt(
        tenant_id=tenant_id,
        grn_number="GRN-PR-LOC-1",
        purchase_order_id=po.id,
        supplier_id=supplier.id,
        warehouse_id=wh_a.id,
        status="posted",
    )
    db_session.add(grn)
    await db_session.flush()
    gi = m.GoodsReceiptItem(
        tenant_id=tenant_id,
        goods_receipt_id=grn.id,
        po_item_id=po_item.id,
        product_id=product.id,
        received_qty=10,
        accepted_qty=10,
        rejected_qty=0,
    )
    db_session.add(gi)
    await db_session.flush()

    ret_a = m.PurchaseReturn(
        tenant_id=tenant_id,
        return_number="PR-LOC-A1",
        supplier_id=supplier.id,
        purchase_order_id=po.id,
        goods_receipt_id=grn.id,
        warehouse_id=wh_a.id,
        status="posted",
        reason="damaged",
        subtotal=30,
        tax_amount=0,
        total_amount=30,
        posted_at=datetime.utcnow(),
    )
    ret_b = m.PurchaseReturn(
        tenant_id=tenant_id,
        return_number="PR-LOC-B1",
        supplier_id=supplier.id,
        purchase_order_id=po.id,
        goods_receipt_id=grn.id,
        warehouse_id=wh_b.id,
        status="posted",
        reason="quality",
        subtotal=12,
        tax_amount=0,
        total_amount=12,
        posted_at=datetime.utcnow(),
    )
    db_session.add_all([ret_a, ret_b])
    await db_session.flush()
    for ret, amount, qty in ((ret_a, 30.0, 3.0), (ret_b, 12.0, 1.0)):
        db_session.add(
            m.PurchaseReturnItem(
                tenant_id=tenant_id,
                purchase_return_id=ret.id,
                goods_receipt_item_id=gi.id,
                product_id=product.id,
                quantity=qty,
                unit_price=10,
                tax_rate=0,
                line_total=amount,
            )
        )
    await db_session.commit()

    by_wh = await ac.get(
        f"/api/v1/reports/purchases/returns?warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert by_wh.status_code == 200, by_wh.text
    wdata = by_wh.json()["data"]
    assert wdata["warehouse_id"] == wh_a.id
    assert wdata["warehouse_name"] == "WH PR A"
    assert wdata["store_id"] == store_a.id
    assert wdata["return_count"] == 1
    assert abs(float(wdata["total_amount"]) - 30) < 0.01
    assert wdata["returns"][0]["return_number"] == "PR-LOC-A1"

    by_store = await ac.get(
        f"/api/v1/reports/purchases/returns?store_id={store_b.id}",
        headers=headers,
    )
    assert by_store.status_code == 200, by_store.text
    sdata = by_store.json()["data"]
    assert sdata["store_id"] == store_b.id
    assert sdata["store_name"] == "PR Store B"
    assert sdata["return_count"] == 1
    assert abs(float(sdata["total_amount"]) - 12) < 0.01

    mismatch = await ac.get(
        f"/api/v1/reports/purchases/returns?store_id={store_b.id}&warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert mismatch.status_code == 400

    missing = await ac.get(
        "/api/v1/reports/purchases/returns?warehouse_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
