"""GRN printable slip with batch, expiry, and rejected quantities."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import models as m
from app.purchasing import render_grn_text
from tests.conftest import auth_headers


def test_render_grn_text_includes_batch_expiry_and_reject():
    text = render_grn_text(
        {
            "grn_number": "GRN-2026-0009",
            "status": "posted",
            "created_at": "2026-08-20T09:15:00",
            "notes": "Dock 2",
            "items": [
                {
                    "product_id": "p1",
                    "received_qty": 50,
                    "accepted_qty": 48,
                    "rejected_qty": 2,
                    "rejection_reason": "damaged",
                    "batch_number": "LOT-2026-A",
                    "expiry_date": "2027-01-15T00:00:00",
                }
            ],
        },
        supplier_name="Acme Supply",
        company_name="Alpha Co",
        po_number="PO-0042",
        warehouse_name="Main WH",
        product_labels={"p1": "SKU-1 Rice"},
    )
    assert "GOODS RECEIVED NOTE GRN-2026-0009" in text
    assert "PO: PO-0042" in text
    assert "Supplier: Acme Supply" in text
    assert "Warehouse: Main WH" in text
    assert "LOT-2026-A" in text
    assert "2027-01-15" in text
    assert "Rejected: damaged" in text
    assert "SKU-1 Rice" in text
    assert "Dock 2" in text


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_grn_print_includes_batch_and_rejects_cross_tenant(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = True
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "GRN Print Sup"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 20, "unit_price": 3}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_number = po.json()["data"]["po_number"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    expiry = (datetime.utcnow() + timedelta(days=60)).isoformat()
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 20,
                    "accepted_qty": 18,
                    "rejected_qty": 2,
                    "rejection_reason": "crushed cartons",
                    "batch_number": "LOT-PRINT-1",
                    "expiry_date": expiry,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]
    grn_number = grn.json()["data"]["grn_number"]

    printed = await ac.get(f"/api/v1/purchasing/grn/{grn_id}/print", headers=headers)
    assert printed.status_code == 200, printed.text
    body = printed.json()["data"]
    assert body["po_number"] == po_number
    assert body["supplier_name"] == "GRN Print Sup"
    assert body["company_name"]
    text = body["text"]
    assert f"GOODS RECEIVED NOTE {grn_number}" in text
    assert po_number in text
    assert "LOT-PRINT-1" in text
    assert "crushed cartons" in text
    assert expiry[:10] in text
    assert "Alpha Co" in text or body["company_name"] in text

    missing = await ac.get(
        "/api/v1/purchasing/grn/00000000-0000-4000-8000-000000000099/print",
        headers=headers,
    )
    assert missing.status_code == 404

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    foreign = await ac.get(f"/api/v1/purchasing/grn/{grn_id}/print", headers=beta)
    assert foreign.status_code in {403, 404}
