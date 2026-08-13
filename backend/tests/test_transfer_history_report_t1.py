"""Inter-store transfer history report (BR-13.2)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import apply_warehouse_stock_change
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_transfer_history_filters_and_aggregates(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    from_store = await create_store(
        db_session, tenant_id=tenant_id, name="Report Src", code="RSRC"
    )
    to_store = await create_store(
        db_session, tenant_id=tenant_id, name="Report Dst", code="RDST"
    )
    other = await create_store(
        db_session, tenant_id=tenant_id, name="Other", code="ROTH"
    )
    await db_session.commit()

    wh = await warehouse_for_store(db_session, tenant_id, from_store.id)
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=tenant_id,
        warehouse_id=wh.id,
        product_id=product.id,
        quantity_delta=50,
    )
    product.stock_qty = float(product.stock_qty or 0) + 50
    await db_session.commit()

    # Create via API (submit=True → requested)
    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": product.id, "quantity": 5}],
        },
    )
    assert created.status_code == 200, created.text
    requested_id = created.json()["data"]["id"]

    draft = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": from_store.id,
            "to_store_id": other.id,
            "submit": False,
            "items": [{"product_id": product.id, "quantity": 2}],
        },
    )
    assert draft.status_code == 200, draft.text
    draft_id = draft.json()["data"]["id"]

    wh_to = await warehouse_for_store(db_session, tenant_id, to_store.id)
    received = m.StockTransfer(
        tenant_id=tenant_id,
        transfer_number="XFER-HIST-R",
        from_store_id=from_store.id,
        to_store_id=to_store.id,
        from_warehouse_id=wh.id,
        to_warehouse_id=wh_to.id,
        status="received",
    )
    db_session.add(received)
    await db_session.flush()
    db_session.add(
        m.StockTransferItem(
            tenant_id=tenant_id,
            transfer_id=received.id,
            product_id=product.id,
            quantity=3,
            shipped_qty=3,
            received_qty=3,
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/reports/inventory/transfers", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    ids = {t["id"] for t in data["transfers"]}
    assert requested_id in ids
    assert draft_id in ids
    assert received.id in ids
    assert data["transfer_count"] >= 3
    assert data["by_status"].get("requested", 0) >= 1
    assert data["by_status"].get("draft", 0) >= 1
    assert data["by_status"].get("received", 0) >= 1
    route = next(
        x
        for x in data["by_route"]
        if x["from_store_id"] == from_store.id and x["to_store_id"] == to_store.id
    )
    assert route["transfer_count"] >= 2

    only_received = await ac.get(
        "/api/v1/reports/inventory/transfers?status=received",
        headers=headers,
    )
    assert only_received.status_code == 200
    assert all(t["status"] == "received" for t in only_received.json()["data"]["transfers"])

    by_to = await ac.get(
        f"/api/v1/reports/inventory/transfers?to_store_id={other.id}",
        headers=headers,
    )
    assert by_to.status_code == 200
    assert all(t["to_store_id"] == other.id for t in by_to.json()["data"]["transfers"])
    assert draft_id in {t["id"] for t in by_to.json()["data"]["transfers"]}

    bad = await ac.get(
        "/api/v1/reports/inventory/transfers?status=bogus",
        headers=headers,
    )
    assert bad.status_code == 400

    # cashier cannot read reports
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/reports/inventory/transfers", headers=cashier)
    assert denied.status_code == 403


def test_flatten_transfers_export():
    from app.report_export import EXPORTABLE, flatten_report

    assert "inventory_transfers" in EXPORTABLE
    rows, lines, title = flatten_report(
        "inventory_transfers",
        {
            "transfer_count": 1,
            "transfers": [
                {
                    "transfer_number": "XFER-1",
                    "from_store_code": "A",
                    "to_store_code": "B",
                    "status": "received",
                    "quantity": 4,
                }
            ],
        },
    )
    assert title == "Inter-Store Transfers"
    assert rows[0]["transfer_number"] == "XFER-1"
    assert any("XFER-1" in line for line in lines)
