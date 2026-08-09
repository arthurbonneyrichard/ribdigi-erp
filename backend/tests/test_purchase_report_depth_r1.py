"""Stage 9 R1: purchase report depth — pending POs + return summary (BR-14.3)."""

from __future__ import annotations

import pytest

from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_pending_orders_and_return_summary(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product_id = str(seed["p1"].id)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "R1 Pending Sup"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    # Fully received PO — must not appear in pending
    po_done = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 4, "unit_price": 10}],
        },
    )
    assert po_done.status_code == 200, po_done.text
    po_done_id = po_done.json()["data"]["id"]
    po_done_item = po_done.json()["data"]["items"][0]["id"]
    assert (await ac.post(f"/api/v1/purchasing/orders/{po_done_id}/send", headers=headers)).status_code == 200
    grn_full = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_done_id,
            "items": [
                {
                    "po_item_id": po_done_item,
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn_full.status_code == 200, grn_full.text

    # Partial receive — pending with open qty
    po_partial = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 10, "unit_price": 5}],
        },
    )
    assert po_partial.status_code == 200, po_partial.text
    po_partial_id = po_partial.json()["data"]["id"]
    po_partial_item = po_partial.json()["data"]["items"][0]["id"]
    assert (
        await ac.post(f"/api/v1/purchasing/orders/{po_partial_id}/send", headers=headers)
    ).status_code == 200
    grn_partial = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_partial_id,
            "items": [
                {
                    "po_item_id": po_partial_item,
                    "received_qty": 3,
                    "accepted_qty": 3,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn_partial.status_code == 200, grn_partial.text

    # Sent, not received — pending
    po_open = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 2, "unit_price": 8}],
        },
    )
    assert po_open.status_code == 200, po_open.text
    po_open_id = po_open.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/purchasing/orders/{po_open_id}/send", headers=headers)).status_code == 200

    # Draft — not pending
    draft = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 1}],
        },
    )
    assert draft.status_code == 200, draft.text

    pending = await ac.get("/api/v1/reports/purchases/pending-orders", headers=headers)
    assert pending.status_code == 200, pending.text
    body = pending.json()["data"]
    ids = {o["id"] for o in body["orders"]}
    assert po_partial_id in ids
    assert po_open_id in ids
    assert po_done_id not in ids
    assert draft.json()["data"]["id"] not in ids
    assert body["count"] >= 2

    partial_row = next(o for o in body["orders"] if o["id"] == po_partial_id)
    assert partial_row["status"] == "partially_received"
    assert partial_row["ordered_qty"] == pytest.approx(10.0)
    assert partial_row["received_qty"] == pytest.approx(3.0)
    assert partial_row["open_qty"] == pytest.approx(7.0)

    open_row = next(o for o in body["orders"] if o["id"] == po_open_id)
    assert open_row["status"] == "sent"
    assert open_row["open_qty"] == pytest.approx(2.0)

    # Purchase return against fully received GRN
    grn_items = grn_full.json()["data"]["items"]
    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=headers,
        json={
            "goods_receipt_id": grn_full.json()["data"]["id"],
            "reason": "quality",
            "items": [{"goods_receipt_item_id": grn_items[0]["id"], "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    return_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/purchasing/returns/{return_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    returns = await ac.get("/api/v1/reports/purchases/returns", headers=headers)
    assert returns.status_code == 200, returns.text
    rbody = returns.json()["data"]
    assert rbody["return_count"] >= 1
    assert rbody["posted_count"] >= 1
    assert any(r["reason"] == "quality" for r in rbody["by_reason"])
    assert any(r["id"] == return_id for r in rbody["returns"])
    assert rbody["posted_amount"] >= float(posted.json()["data"]["total_amount"])


@pytest.mark.asyncio
async def test_purchase_report_depth_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product_id = str(seed["p1"].id)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "R1 Iso Sup"},
    )
    supplier_id = supplier.json()["data"]["id"]
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 3, "unit_price": 2}],
        },
    )
    po_id = po.json()["data"]["id"]
    await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    cross = await ac.get("/api/v1/reports/purchases/pending-orders", headers=beta)
    assert cross.status_code in (200, 403)
    if cross.status_code == 200:
        ids = {o["id"] for o in cross.json()["data"]["orders"]}
        assert po_id not in ids

    # Beta cashier lacks reports:read in default RBAC — also cover returns endpoint
    cross_ret = await ac.get("/api/v1/reports/purchases/returns", headers=beta)
    assert cross_ret.status_code in (200, 403)
    if cross_ret.status_code == 200:
        assert all(r["supplier_id"] != supplier_id for r in cross_ret.json()["data"]["returns"])


@pytest.mark.asyncio
async def test_purchase_report_export_types(client):
    from app.report_export import EXPORTABLE, flatten_report

    assert "purchases_pending_orders" in EXPORTABLE
    assert "purchases_returns" in EXPORTABLE
    rows, lines, title = flatten_report(
        "purchases_pending_orders",
        {
            "count": 1,
            "open_qty": 5,
            "orders": [
                {
                    "po_number": "PO-1",
                    "supplier_name": "Acme",
                    "open_qty": 5,
                    "status": "sent",
                }
            ],
        },
    )
    assert title == "Pending Purchase Orders"
    assert rows[0]["po_number"] == "PO-1"
    assert any("PO-1" in line for line in lines)
