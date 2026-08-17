"""Purchase returns summary report (BR-14.3)."""

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
async def test_returns_summary_by_reason_and_filters(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    supplier = m.Party(
        tenant_id=tenant_id, name="Return Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number="PO-RET-1",
        supplier_id=supplier.id,
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
        grn_number="GRN-RET-1",
        purchase_order_id=po.id,
        supplier_id=supplier.id,
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

    specs = [
        ("PR-1", "damaged", "posted", 40.0, 2.0),
        ("PR-2", "damaged", "draft", 10.0, 1.0),
        ("PR-3", "expiry", "posted", 25.0, 1.0),
        ("PR-4", "quality", "cancelled", 5.0, 1.0),
    ]
    for number, reason, status, amount, qty in specs:
        ret = m.PurchaseReturn(
            tenant_id=tenant_id,
            return_number=number,
            supplier_id=supplier.id,
            purchase_order_id=po.id,
            goods_receipt_id=grn.id,
            status=status,
            reason=reason,
            subtotal=amount,
            tax_amount=0,
            total_amount=amount,
            posted_at=datetime.utcnow() if status == "posted" else None,
        )
        db_session.add(ret)
        await db_session.flush()
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

    r = await ac.get("/api/v1/reports/purchases/returns", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["return_count"] == 4
    assert abs(float(data["total_amount"]) - 80) < 0.01
    assert abs(float(data["posted_amount"]) - 65) < 0.01
    damaged = next(x for x in data["by_reason"] if x["reason"] == "damaged")
    assert damaged["return_count"] == 2
    assert abs(float(damaged["total_amount"]) - 50) < 0.01
    assert abs(float(damaged["quantity"]) - 3) < 0.01
    assert data["by_status"].get("posted") == 2
    assert data["by_status"].get("draft") == 1
    assert data["by_supplier"][0]["name"] == "Return Supplier"

    only_damaged = await ac.get(
        "/api/v1/reports/purchases/returns?reason=damaged",
        headers=headers,
    )
    assert only_damaged.status_code == 200
    assert only_damaged.json()["data"]["return_count"] == 2
    assert all(x["reason"] == "damaged" for x in only_damaged.json()["data"]["returns"])

    only_posted = await ac.get(
        "/api/v1/reports/purchases/returns?status=posted",
        headers=headers,
    )
    assert only_posted.status_code == 200
    assert only_posted.json()["data"]["return_count"] == 2

    bad = await ac.get(
        "/api/v1/reports/purchases/returns?reason=not-a-reason",
        headers=headers,
    )
    assert bad.status_code == 422


def test_flatten_returns_export():
    from app.report_export import EXPORTABLE, flatten_report

    assert "purchases_returns" in EXPORTABLE
    rows, lines, title = flatten_report(
        "purchases_returns",
        {
            "return_count": 1,
            "returns": [
                {
                    "return_number": "PR-9",
                    "supplier_name": "Acme",
                    "reason": "damaged",
                    "status": "posted",
                    "total_amount": 12,
                }
            ],
        },
    )
    assert title == "Purchase Returns Summary"
    assert rows[0]["return_number"] == "PR-9"
    assert any("PR-9" in line for line in lines)
