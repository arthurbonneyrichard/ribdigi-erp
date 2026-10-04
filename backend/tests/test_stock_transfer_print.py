"""Stock transfer printable slip for warehouse / inter-store desks."""

from __future__ import annotations

import pytest

from app import models as m
from app.inventory import apply_stock_change
from app.stores import render_stock_transfer_text
from tests.conftest import auth_headers


def test_render_stock_transfer_text_includes_locations_and_qtys():
    text = render_stock_transfer_text(
        {
            "transfer_number": "TR-20260820-0001",
            "status": "in_transit",
            "created_at": "2026-08-20T08:00:00",
            "shipped_at": "2026-08-20T09:00:00",
            "notes": "Rush restock",
            "items": [
                {
                    "product_id": "p1",
                    "quantity": 20,
                    "shipped_qty": 20,
                    "received_qty": 0,
                }
            ],
        },
        company_name="Alpha Co",
        from_label="Warehouse WHA Main",
        to_label="Warehouse WHB Branch",
        product_labels={"p1": "A-1 Alpha Widget"},
    )
    assert "STOCK TRANSFER TR-20260820-0001" in text
    assert "From: Warehouse WHA Main" in text
    assert "To: Warehouse WHB Branch" in text
    assert "A-1 Alpha Widget" in text
    assert "Rush restock" in text
    assert "in_transit" in text


@pytest.mark.asyncio
async def test_stock_transfer_print_and_foreign_404(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    wh_a = m.Warehouse(
        tenant_id=seed["t1"].id, company_id=seed["c1"].id, name="Print WH A", code="PWA"
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id, company_id=seed["c1"].id, name="Print WH B", code="PWB"
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=30,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh_a.id,
        company_id=seed["c1"].id,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": wh_a.id,
            "to_warehouse_id": wh_b.id,
            "submit": True,
            "notes": "Print desk copy",
            "items": [{"product_id": seed["p1"].id, "quantity": 5}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]
    transfer_number = created.json()["data"]["transfer_number"]

    printed = await ac.get(
        f"/api/v1/inventory/stock-transfers/{transfer_id}/print", headers=headers
    )
    assert printed.status_code == 200, printed.text
    body = printed.json()["data"]
    assert transfer_number in body["text"]
    assert "Print WH A" in body["text"] or "PWA" in body["text"]
    assert "Print WH B" in body["text"] or "PWB" in body["text"]
    assert "Print desk copy" in body["text"]
    assert body["transfer"]["id"] == transfer_id

    foreign_wh_a = m.Warehouse(
        tenant_id=seed["t2"].id, company_id=seed["c2"].id, name="Beta A", code="BA"
    )
    foreign_wh_b = m.Warehouse(
        tenant_id=seed["t2"].id, company_id=seed["c2"].id, name="Beta B", code="BB"
    )
    db_session.add_all([foreign_wh_a, foreign_wh_b])
    await db_session.flush()
    foreign = m.StockTransfer(
        tenant_id=seed["t2"].id,
        company_id=seed["c2"].id,
        transfer_number="TR-BETA-SECRET",
        from_warehouse_id=foreign_wh_a.id,
        to_warehouse_id=foreign_wh_b.id,
        status="draft",
        created_by=seed["u2"].id,
    )
    db_session.add(foreign)
    await db_session.commit()
    leak = await ac.get(
        f"/api/v1/inventory/stock-transfers/{foreign.id}/print", headers=headers
    )
    assert leak.status_code == 404
