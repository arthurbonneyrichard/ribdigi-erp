"""Pending purchase orders report (BR-14.3)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pending_orders_excludes_received_and_cancelled(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Pending PO Supplier", "credit_limit": 0},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    async def create_po() -> str:
        r = await ac.post(
            "/api/v1/purchasing/orders",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": 10,
                        "unit_price": 5,
                        "tax_rate": 0,
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["id"]

    draft_id = await create_po()
    sent_id = await create_po()
    partial_id = await create_po()
    received_id = await create_po()
    cancelled_id = await create_po()

    async def set_status(po_id: str, status: str, received_qty: float | None = None):
        po = (
            await db_session.execute(select(m.PurchaseOrder).where(m.PurchaseOrder.id == po_id))
        ).scalar_one()
        po.status = status
        if received_qty is not None:
            item = (
                await db_session.execute(
                    select(m.PurchaseOrderItem).where(
                        m.PurchaseOrderItem.purchase_order_id == po_id
                    )
                )
            ).scalar_one()
            item.received_qty = received_qty

    await set_status(sent_id, "sent")
    await set_status(partial_id, "partially_received", received_qty=4)
    await set_status(received_id, "received", received_qty=10)
    await set_status(cancelled_id, "cancelled")
    await db_session.commit()

    r = await ac.get("/api/v1/reports/purchases/pending-orders", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    ids = {o["id"] for o in data["orders"]}
    assert draft_id in ids
    assert sent_id in ids
    assert partial_id in ids
    assert received_id not in ids
    assert cancelled_id not in ids

    partial = next(o for o in data["orders"] if o["id"] == partial_id)
    assert abs(float(partial["outstanding_qty"]) - 6) < 0.01
    assert partial["status"] == "partially_received"
    assert data["by_status"].get("draft", 0) >= 1
    assert data["by_status"].get("sent", 0) >= 1
    assert data["by_status"].get("partially_received", 0) >= 1

    only_sent = await ac.get(
        "/api/v1/reports/purchases/pending-orders?status=sent",
        headers=headers,
    )
    assert only_sent.status_code == 200
    assert all(o["status"] == "sent" for o in only_sent.json()["data"]["orders"])

    bad = await ac.get(
        "/api/v1/reports/purchases/pending-orders?status=received",
        headers=headers,
    )
    assert bad.status_code == 400


def test_flatten_pending_orders_export():
    from app.report_export import EXPORTABLE, flatten_report

    assert "purchases_pending_orders" in EXPORTABLE
    rows, lines, title = flatten_report(
        "purchases_pending_orders",
        {
            "order_count": 1,
            "orders": [
                {
                    "po_number": "PO-1",
                    "supplier_name": "Acme",
                    "status": "sent",
                    "outstanding_qty": 3,
                    "total_amount": 50,
                }
            ],
        },
    )
    assert title == "Pending Purchase Orders"
    assert rows[0]["po_number"] == "PO-1"
    assert any("PO-1" in line for line in lines)
