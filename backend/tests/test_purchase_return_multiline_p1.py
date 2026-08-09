"""Stage 8 P1: purchase return multi-line create (API already multi-line; UI uses it)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_purchase_return_create_multiple_lines(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product_a = str(seed["p1"].id)

    from app import models as m

    p2 = m.Product(
        tenant_id=seed["t1"].id,
        name="Return Line B",
        sku="RET-B-1",
        cost_price=3,
        selling_price=5,
        stock_qty=0,
    )
    db_session.add(p2)
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Multi-line Return Sup"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {"product_id": product_a, "quantity": 10, "unit_price": 4},
                {"product_id": p2.id, "quantity": 6, "unit_price": 3},
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_items = po.json()["data"]["items"]
    assert len(po_items) == 2

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_items[0]["id"],
                    "received_qty": 10,
                    "accepted_qty": 10,
                    "rejected_qty": 0,
                },
                {
                    "po_item_id": po_items[1]["id"],
                    "received_qty": 6,
                    "accepted_qty": 6,
                    "rejected_qty": 0,
                },
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]
    grn_items = grn.json()["data"]["items"]
    assert len(grn_items) == 2

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers,
        json={
            "goods_receipt_id": grn_id,
            "reason": "quality",
            "items": [
                {"goods_receipt_item_id": grn_items[0]["id"], "quantity": 3},
                {"goods_receipt_item_id": grn_items[1]["id"], "quantity": 2},
            ],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["status"] == "draft"
    assert len(body["items"]) == 2
    qtys = sorted(float(i["quantity"]) for i in body["items"])
    assert qtys == [2.0, 3.0]
    assert float(body["total_amount"]) == pytest.approx(3 * 4 + 2 * 3)

    listed = await ac.get("/api/v1/purchasing/returns", headers=headers)
    assert listed.status_code == 200
    row = next(r for r in listed.json()["data"] if r["id"] == body["id"])
    assert len(row["items"]) == 2
