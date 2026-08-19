"""GRN partial receive with rejected qty and batch/expiry stock-in."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_grn_partial_accept_reject_with_batch(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = True
    product.stock_qty = 0
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Batch Supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 50,
                    "unit_price": 2,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    expiry = (datetime.utcnow() + timedelta(days=90)).isoformat()
    # Missing batch on batch-tracked product
    missing_batch = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 50,
                    "accepted_qty": 48,
                    "rejected_qty": 2,
                    "rejection_reason": "damaged",
                }
            ],
        },
    )
    assert missing_batch.status_code == 400

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 50,
                    "accepted_qty": 48,
                    "rejected_qty": 2,
                    "rejection_reason": "damaged",
                    "batch_number": "LOT-2026-A",
                    "expiry_date": expiry,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    data = grn.json()["data"]
    assert data["items"][0]["accepted_qty"] == 48
    assert data["items"][0]["rejected_qty"] == 2
    assert data["items"][0]["batch_number"] == "LOT-2026-A"
    assert data["items"][0]["batch_id"]

    refreshed = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["status"] == "partially_received"
    assert refreshed.json()["data"]["items"][0]["received_qty"] == 48
    assert refreshed.json()["data"]["items"][0]["outstanding_qty"] == 2

    product = await db_session.get(m.Product, seed["p1"].id)
    await db_session.refresh(product)
    assert float(product.stock_qty) == 48

    batch = (
        await db_session.execute(
            select(m.ProductBatch).where(
                m.ProductBatch.tenant_id == seed["t1"].id,
                m.ProductBatch.batch_number == "LOT-2026-A",
            )
        )
    ).scalar_one()
    assert float(batch.quantity) == 48
    assert batch.expiry_date is not None

    # Rejected qty without reason
    bad_reason = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 2,
                    "accepted_qty": 0,
                    "rejected_qty": 2,
                    "batch_number": "LOT-2026-B",
                }
            ],
        },
    )
    assert bad_reason.status_code == 400
