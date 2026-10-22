"""Server-issued offline grants, expiry, revalidation, multi-device allocations, and restore.

Covers the offline POS acceptance list: expiry blocks new sales but keeps the queue,
reconnect after expiry revalidates and syncs, failed retries never duplicate, two
offline devices cannot oversell, conflicts stay visible until an authorised user
resolves them, tenant isolation, and an isolated restore neither erases nor
duplicates pending sales.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import func, select

from app import models as m
from app.offline_pos import OFFLINE_COMPLETE_MISSING
from tests.conftest import auth_headers, set_tenant_industry


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _beta_cashier(ac):
    return await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


async def _store_with_stock(ac, db_session, seed, admin, *, qty: float, code: str = "OFF1") -> str:
    from app import stores as stores_svc

    created = await ac.post("/api/v1/stores", headers=admin, json={"code": code, "name": f"Store {code}"})
    assert created.status_code == 200, created.text
    store_id = created.json()["data"]["id"]
    assigned = await ac.put(
        f"/api/v1/users/{seed['u1'].id}/stores", headers=admin, json={"store_ids": [store_id]}
    )
    assert assigned.status_code == 200, assigned.text
    wh = await stores_svc.warehouse_for_store(db_session, seed["t1"].id, store_id)
    row = (
        await db_session.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.warehouse_id == wh.id,
                m.WarehouseStock.product_id == seed["p1"].id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = m.WarehouseStock(
            tenant_id=seed["t1"].id, warehouse_id=wh.id, product_id=seed["p1"].id, quantity=qty
        )
        db_session.add(row)
    else:
        row.quantity = qty
    product = seed["p1"]
    product.stock_qty = qty
    product.selling_price = 10
    await db_session.commit()
    return store_id


async def _open_shift(ac, headers, closer=None) -> str:
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close", headers=closer or headers, json={"actual_cash": 0}
            )
    opened = await ac.post("/api/v1/pos/sessions/open", headers=headers, json={"opening_cash": 0})
    assert opened.status_code == 200, opened.text
    return opened.json()["data"].get("session_id") or opened.json()["data"]["id"]


async def _authorize(ac, headers, device_id: str, store_id: str | None, **extra):
    r = await ac.post(
        "/api/v1/pos/offline/authorize",
        headers=headers,
        json={"device_id": device_id, "store_id": store_id, **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _sale(session_id, crid, device_id, grant_id, product_id, qty=1, price=10, **extra):
    body = {
        "session_id": session_id,
        "client_request_id": crid,
        "offline_sync": True,
        "offline_created_at": datetime.utcnow().isoformat(),
        "device_id": device_id,
        "offline_grant_id": grant_id,
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product_id, "quantity": qty, "unit_price": price}],
    }
    body.update(extra)
    return body


async def _count_sales(db_session, crid: str) -> int:
    return int(
        (
            await db_session.execute(
                select(func.count(m.Transaction.id)).where(m.Transaction.client_request_id == crid)
            )
        ).scalar()
        or 0
    )


async def _warehouse_qty(db_session, store_id: str, product_id: str) -> float:
    wh = (
        await db_session.execute(select(m.Warehouse).where(m.Warehouse.store_id == store_id))
    ).scalar_one()
    row = (
        await db_session.execute(
            select(m.WarehouseStock)
            .where(m.WarehouseStock.warehouse_id == wh.id, m.WarehouseStock.product_id == product_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return float(row.quantity)


@pytest.mark.asyncio
async def test_grant_is_server_issued_device_bound_and_allocates_stock(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    grant = await _authorize(ac, cashier, "dev-grant-a0001", store_id)
    assert grant["device_id"] == "dev-grant-a0001"
    assert grant["store_id"] == store_id
    assert grant["user_id"] == seed["u1"].id
    assert "pos_sale" in grant["allowed_actions"]
    assert "credit_sale" in grant["allowed_actions"]
    assert "resolve_conflicts" not in grant["allowed_actions"]
    alloc = {a["product_id"]: a for a in grant["allocations"]}
    assert alloc[seed["p1"].id]["allocated_qty"] == 5
    assert grant["recent_changes_notice"]

    status = await ac.post(
        "/api/v1/pos/offline/status",
        headers=cashier,
        json={"device_id": "dev-grant-a0001", "client_request_ids": []},
    )
    assert status.status_code == 200, status.text
    assert status.json()["data"]["grant_active"] is True

    beta = await _beta_cashier(ac)
    stolen = await ac.post(
        "/api/v1/pos/offline/authorize",
        headers=beta,
        json={"device_id": "dev-grant-b0001", "store_id": store_id},
    )
    assert stolen.status_code in {403, 404}


@pytest.mark.asyncio
async def test_expired_grant_still_syncs_sales_made_inside_window(client, db_session):
    """Expiry blocks new offline sales on the device; it never strands the queue."""
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    grant = await _authorize(ac, cashier, "dev-expiry-0001", store_id)
    inside = _sale(session_id, "cr-expiry-inside-01", "dev-expiry-0001", grant["grant_id"], seed["p1"].id)

    row = await db_session.get(m.OfflineGrant, grant["grant_id"])
    row.issued_at = datetime.utcnow() - timedelta(hours=10)
    row.valid_until = datetime.utcnow() - timedelta(hours=2)
    await db_session.commit()
    inside["offline_created_at"] = (datetime.utcnow() - timedelta(hours=5)).isoformat()

    synced = await ac.post("/api/v1/pos/sales", headers=cashier, json=inside)
    assert synced.status_code == 200, synced.text
    assert await _count_sales(db_session, "cr-expiry-inside-01") == 1

    after = _sale(session_id, "cr-expiry-after-001", "dev-expiry-0001", grant["grant_id"], seed["p1"].id)
    rejected = await ac.post("/api/v1/pos/sales", headers=cashier, json=after)
    assert rejected.status_code == 403, rejected.text
    detail = rejected.json()["detail"]
    assert detail["code"] == "OFFLINE_SALE_OUTSIDE_GRANT"
    assert detail["kept"] is True
    event_id = detail["sync_event_id"]
    assert await _count_sales(db_session, "cr-expiry-after-001") == 0

    listed = await ac.get("/api/v1/pos/offline/conflicts", headers=admin)
    assert any(e["id"] == event_id for e in listed.json()["data"])

    cashier_resolve = await ac.post(
        f"/api/v1/pos/offline/conflicts/{event_id}/resolve",
        headers=cashier,
        json={"action": "approve_outside_window", "note": "self approve"},
    )
    assert cashier_resolve.status_code == 403

    resolved = await ac.post(
        f"/api/v1/pos/offline/conflicts/{event_id}/resolve",
        headers=admin,
        json={"action": "approve_outside_window", "note": "Till clock was wrong, sale confirmed"},
    )
    assert resolved.status_code == 200, resolved.text
    after["resolution_event_id"] = event_id
    ok = await ac.post("/api/v1/pos/sales", headers=cashier, json=after)
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["offline_sync"] is True
    assert await _count_sales(db_session, "cr-expiry-after-001") == 1


@pytest.mark.asyncio
async def test_revalidate_after_expiry_supersedes_grant_and_old_queue_syncs(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    first = await _authorize(ac, cashier, "dev-reval-00001", store_id)
    queued = _sale(session_id, "cr-reval-queued-01", "dev-reval-00001", first["grant_id"], seed["p1"].id)

    row = await db_session.get(m.OfflineGrant, first["grant_id"])
    row.valid_until = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    second = await _authorize(
        ac, cashier, "dev-reval-00001", store_id, pending_items={seed["p1"].id: 1}
    )
    assert second["grant_id"] != first["grant_id"]
    old = await db_session.get(m.OfflineGrant, first["grant_id"], populate_existing=True)
    assert old.revoked_at is not None and old.revoke_reason == "superseded"
    alloc = {a["product_id"]: a for a in second["allocations"]}
    assert alloc[seed["p1"].id]["allocated_qty"] == 4

    synced = await ac.post("/api/v1/pos/sales", headers=cashier, json=queued)
    assert synced.status_code == 200, synced.text


@pytest.mark.asyncio
async def test_failed_retry_never_duplicates_sale_payment_or_stock(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    grant = await _authorize(ac, cashier, "dev-retry-00001", store_id)
    body = _sale(
        session_id, "cr-retry-dup-0001", "dev-retry-00001", grant["grant_id"], seed["p1"].id, price=99
    )
    conflict = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    assert conflict.status_code == 409
    again = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    assert again.status_code == 409
    assert again.json()["detail"]["sync_event_id"] == conflict.json()["detail"]["sync_event_id"]
    assert await _count_sales(db_session, "cr-retry-dup-0001") == 0
    assert await _warehouse_qty(db_session, store_id, seed["p1"].id) == 10

    event_id = conflict.json()["detail"]["sync_event_id"]
    resolved = await ac.post(
        f"/api/v1/pos/offline/conflicts/{event_id}/resolve",
        headers=admin,
        json={"action": "approve_server_price", "note": "Shelf label was stale"},
    )
    assert resolved.status_code == 200, resolved.text
    body["resolution_event_id"] = event_id
    first = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["total"] == 10
    for _ in range(3):
        replay = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
        assert replay.status_code == 200
        assert replay.json()["data"]["idempotent_replay"] is True
    assert await _count_sales(db_session, "cr-retry-dup-0001") == 1
    sale_id = first.json()["data"]["id"]
    payments = (
        await db_session.execute(select(func.count(m.PosPayment.id)).where(m.PosPayment.sale_id == sale_id))
    ).scalar()
    assert payments == 1
    assert await _warehouse_qty(db_session, store_id, seed["p1"].id) == 9


@pytest.mark.asyncio
async def test_two_offline_devices_cannot_oversell_and_conflict_is_visible(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    a = await _authorize(ac, cashier, "dev-multi-aaaa1", store_id)
    b = await _authorize(ac, cashier, "dev-multi-bbbb1", store_id)
    a_alloc = {x["product_id"]: x["allocated_qty"] for x in a["allocations"]}[seed["p1"].id]
    b_alloc = {x["product_id"]: x["allocated_qty"] for x in b["allocations"]}[seed["p1"].id]
    assert a_alloc == 5
    assert b_alloc == 2
    assert a_alloc + b_alloc <= 10

    # A third, online till cannot take stock held for the offline devices.
    online = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "device_id": "dev-online-c0001",
            "payment_method": "cash",
            "status": "completed",
            "items": [{"product_id": seed["p1"].id, "quantity": 4}],
        },
    )
    assert online.status_code == 409, online.text
    assert online.json()["detail"]["code"] == "INSUFFICIENT_AVAILABLE_STOCK"

    sale_a = _sale(session_id, "cr-multi-a-000001", "dev-multi-aaaa1", a["grant_id"], seed["p1"].id, qty=5)
    ok_a = await ac.post("/api/v1/pos/sales", headers=cashier, json=sale_a)
    assert ok_a.status_code == 200, ok_a.text

    sale_b = _sale(session_id, "cr-multi-b-000001", "dev-multi-bbbb1", b["grant_id"], seed["p1"].id, qty=4)
    over = await ac.post("/api/v1/pos/sales", headers=cashier, json=sale_b)
    assert over.status_code == 409, over.text
    assert over.json()["detail"]["code"] == "ALLOCATION_EXCEEDED"
    assert await _count_sales(db_session, "cr-multi-b-000001") == 0
    assert await _warehouse_qty(db_session, store_id, seed["p1"].id) == 5

    cashier_override = dict(sale_b, allocation_override=True)
    still = await ac.post("/api/v1/pos/sales", headers=cashier, json=cashier_override)
    assert still.status_code == 409

    conflicts = await ac.get("/api/v1/pos/offline/conflicts", headers=admin)
    event = next(e for e in conflicts.json()["data"] if e["client_request_id"] == "cr-multi-b-000001")
    assert "approve_allocation_override" in event["allowed_resolutions"]
    resolved = await ac.post(
        f"/api/v1/pos/offline/conflicts/{event['id']}/resolve",
        headers=admin,
        json={"action": "approve_allocation_override", "note": "Units were on the shelf"},
    )
    assert resolved.status_code == 200
    sale_b["resolution_event_id"] = event["id"]
    ok_b = await ac.post("/api/v1/pos/sales", headers=cashier, json=sale_b)
    assert ok_b.status_code == 200, ok_b.text
    assert await _warehouse_qty(db_session, store_id, seed["p1"].id) == 1

    # Physical stock is never driven negative: a further oversell stays a conflict.
    sale_b2 = _sale(session_id, "cr-multi-b-000002", "dev-multi-bbbb1", b["grant_id"], seed["p1"].id, qty=3)
    blocked = await ac.post("/api/v1/pos/sales", headers=cashier, json=sale_b2)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] in {"STOCK_CONFLICT", "ALLOCATION_EXCEEDED"}
    assert await _warehouse_qty(db_session, store_id, seed["p1"].id) == 1


@pytest.mark.asyncio
async def test_offline_credit_and_bank_tenders_sync_once_gift_card_blocked(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    grant = await _authorize(ac, cashier, "dev-tender-0001", store_id)
    party = seed["party1"]

    credit = _sale(
        session_id, "cr-credit-off-001", "dev-tender-0001", grant["grant_id"], seed["p1"].id,
        payment_method="credit", party_id=party.id,
    )
    r1 = await ac.post("/api/v1/pos/sales", headers=cashier, json=credit)
    assert r1.status_code == 200, r1.text
    r2 = await ac.post("/api/v1/pos/sales", headers=cashier, json=credit)
    assert r2.json()["data"]["idempotent_replay"] is True
    refreshed = await db_session.get(m.Party, party.id, populate_existing=True)
    assert float(refreshed.balance) == 10.0

    bank = _sale(
        session_id, "cr-bank-off-0001", "dev-tender-0001", grant["grant_id"], seed["p1"].id,
        payment_method="bank_transfer",
        payments=[{"payment_method": "bank_transfer", "amount": 10, "reference": "TRF-123"}],
    )
    rb = await ac.post("/api/v1/pos/sales", headers=cashier, json=bank)
    assert rb.status_code == 200, rb.text

    gift = _sale(
        session_id, "cr-gift-off-0001", "dev-tender-0001", grant["grant_id"], seed["p1"].id,
        payment_method="gift_card",
        payments=[{"payment_method": "gift_card", "amount": 10, "reference": "GC-1"}],
    )
    rg = await ac.post("/api/v1/pos/sales", headers=cashier, json=gift)
    assert rg.status_code == 409, rg.text
    assert rg.json()["detail"]["code"] == "OFFLINE_TENDER_NOT_ALLOWED"

    over = _sale(
        session_id, "cr-credit-over-01", "dev-tender-0001", grant["grant_id"], seed["p1"].id,
        qty=1, price=10, payment_method="credit", party_id=party.id,
    )
    refreshed.credit_limit = 12
    await db_session.commit()
    ro = await ac.post("/api/v1/pos/sales", headers=cashier, json=over)
    assert ro.status_code == 409, ro.text
    assert ro.json()["detail"]["code"] == "CREDIT_LIMIT_EXCEEDED"
    event_id = ro.json()["detail"]["sync_event_id"]
    resolved = await ac.post(
        f"/api/v1/pos/offline/conflicts/{event_id}/resolve",
        headers=admin,
        json={"action": "approve_credit_override", "note": "Known customer, manager approved"},
    )
    assert resolved.status_code == 200, resolved.text
    over["resolution_event_id"] = event_id
    ok = await ac.post("/api/v1/pos/sales", headers=cashier, json=over)
    assert ok.status_code == 200, ok.text
    refreshed = await db_session.get(m.Party, party.id, populate_existing=True)
    assert float(refreshed.balance) == 20.0


@pytest.mark.asyncio
async def test_grant_isolation_dismiss_keeps_record_and_closed_shift(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    grant = await _authorize(ac, cashier, "dev-iso-000001", store_id)

    beta = await _beta_cashier(ac)
    beta_session = await _open_shift(ac, beta)
    stolen = _sale(beta_session, "cr-iso-beta-0001", "dev-iso-000001", grant["grant_id"], seed["p2"].id)
    rs = await ac.post("/api/v1/pos/sales", headers=beta, json=stolen)
    assert rs.status_code == 403, rs.text
    assert rs.json()["detail"]["code"] == "OFFLINE_GRANT_INVALID"
    beta_list = await ac.get("/api/v1/pos/offline/conflicts", headers=beta)
    assert all(e["device_id"] != "dev-iso-000001" or e["client_request_id"] == "cr-iso-beta-0001"
               for e in beta_list.json()["data"])
    alpha_list = await ac.get("/api/v1/pos/offline/conflicts", headers=admin)
    assert all(e["client_request_id"] != "cr-iso-beta-0001" for e in alpha_list.json()["data"])

    # Shift closed before sync → sale lands on the cashier's new shift at the same store.
    queued = _sale(session_id, "cr-iso-shift-0001", "dev-iso-000001", grant["grant_id"], seed["p1"].id)
    new_session = await _open_shift(ac, cashier, admin)
    moved = await ac.post("/api/v1/pos/sales", headers=cashier, json=queued)
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["session_id"] == new_session
    assert moved.json()["data"]["original_session_id"] == session_id

    # Dismissed conflict: kept on record, never posted.
    bad = _sale(session_id, "cr-iso-dismiss-01", "dev-iso-000001", grant["grant_id"], seed["p1"].id, price=1)
    rc = await ac.post("/api/v1/pos/sales", headers=cashier, json=bad)
    assert rc.status_code == 409
    event_id = rc.json()["detail"]["sync_event_id"]
    dismissed = await ac.post(
        f"/api/v1/pos/offline/conflicts/{event_id}/resolve",
        headers=admin,
        json={"action": "dismiss", "note": "Training sale, not real"},
    )
    assert dismissed.status_code == 200
    again = await ac.post("/api/v1/pos/sales", headers=cashier, json=bad)
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "SALE_DISMISSED"
    assert await _count_sales(db_session, "cr-iso-dismiss-01") == 0
    history = await ac.get("/api/v1/pos/offline/conflicts?include_resolved=true", headers=admin)
    kept = [e for e in history.json()["data"] if e["client_request_id"] == "cr-iso-dismiss-01"]
    assert kept and any(e["resolution"] == "dismiss" for e in kept)


@pytest.mark.asyncio
async def test_blocked_device_cannot_get_grant(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    await _authorize(ac, cashier, "dev-block-00001", store_id)
    blocked = await ac.post(
        "/api/v1/pos/offline/devices/dev-block-00001/block", headers=admin, json={"blocked": True}
    )
    assert blocked.status_code == 200, blocked.text
    denied = await ac.post(
        "/api/v1/pos/offline/authorize",
        headers=cashier,
        json={"device_id": "dev-block-00001", "store_id": store_id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "DEVICE_BLOCKED"


@pytest.mark.asyncio
async def test_offline_quote_capture_is_idempotent(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    body = {
        "customer_id": seed["party1"].id,
        "client_request_id": "cr-quote-offline-01",
        "items": [{"product_id": seed["p1"].id, "quantity": 3}],
    }
    first = await ac.post("/api/v1/sales/quotations", headers=admin, json=body)
    assert first.status_code == 200, first.text
    second = await ac.post("/api/v1/sales/quotations", headers=admin, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert second.json()["data"]["idempotent_replay"] is True
    count = (
        await db_session.execute(
            select(func.count(m.SalesQuotation.id)).where(
                m.SalesQuotation.client_request_id == "cr-quote-offline-01"
            )
        )
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_offline_catalog_scoped_by_industry(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    retail = await ac.get(f"/api/v1/pos/offline/catalog?store_id={store_id}", headers=cashier)
    assert retail.status_code == 200, retail.text
    data = retail.json()["data"]
    names = {p["name"] for p in data["products"]}
    assert "Alpha Widget" in names and "Beta Widget" not in names
    assert all("Beta" not in c["name"] for c in data["customers"])
    assert data["pharmacy_rules"] is False

    product = seed["p1"]
    product.rx_only = True
    await db_session.commit()
    rx_free = m.Product(
        tenant_id=seed["t1"].id, name="Expired Syrup", sku="EXP-1", selling_price=5, stock_qty=4,
        tracks_batches=True,
    )
    db_session.add(rx_free)
    await db_session.flush()
    db_session.add(
        m.ProductBatch(
            tenant_id=seed["t1"].id, product_id=rx_free.id, batch_number="LOT-OLD",
            expiry_date=datetime.utcnow() - timedelta(days=3), quantity=4,
        )
    )
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    pharm_cashier = await _cashier(ac)
    pharm = await ac.get(f"/api/v1/pos/offline/catalog?store_id={store_id}", headers=pharm_cashier)
    assert pharm.status_code == 200, pharm.text
    rows = {p["name"]: p for p in pharm.json()["data"]["products"]}
    assert rows["Alpha Widget"]["rx_only"] is True
    assert rows["Alpha Widget"]["offline_block_reason"]
    assert rows["Expired Syrup"]["saleable_lots"] == []
    assert rows["Expired Syrup"]["offline_block_reason"]

    await set_tenant_industry(db_session, seed["t1"], "retail_wholesale")
    combo = await ac.get(
        f"/api/v1/pos/offline/catalog?store_id={store_id}", headers=await _cashier(ac)
    )
    assert combo.status_code == 403, combo.text
    detail = combo.json()["detail"]
    assert detail["code"] == "INDUSTRY_MODULE_DISABLED"
    assert detail["module"] == "pos"
    assert detail["industry"] is None
    assert combo.json().get("data", {}).get("wholesale_tiers") is not True
    assert combo.json().get("data", {}).get("pharmacy_rules") is not True


@pytest.mark.asyncio
async def test_isolated_restore_neither_erases_nor_duplicates_pending_sales(
    client, db_session, tmp_path, monkeypatch
):
    """Restore runs against the per-test sqlite database only — never production data."""
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10)
    cashier = await _cashier(ac)
    session_id = await _open_shift(ac, cashier, admin)
    grant = await _authorize(ac, cashier, "dev-restore-0001", store_id)

    backup = await ac.post("/api/v1/backup", headers=admin, json={"notes": "offline-restore-drill"})
    assert backup.status_code == 200, backup.text
    backup_id = backup.json()["data"]["id"]

    synced_before = _sale(session_id, "cr-restore-a-0001", "dev-restore-0001", grant["grant_id"], seed["p1"].id)
    ra = await ac.post("/api/v1/pos/sales", headers=cashier, json=synced_before)
    assert ra.status_code == 200, ra.text
    pending = _sale(session_id, "cr-restore-b-0001", "dev-restore-0001", grant["grant_id"], seed["p1"].id)

    applied = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=admin,
        json={"dry_run": False, "confirm": True, "confirm_text": "RESTORE"},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["proof"]["ok"] is True

    # Device re-sends everything it still holds (already-synced and pending).
    resend_a = await ac.post("/api/v1/pos/sales", headers=cashier, json=synced_before)
    assert resend_a.status_code == 200, resend_a.text
    send_b = await ac.post("/api/v1/pos/sales", headers=cashier, json=pending)
    assert send_b.status_code == 200, send_b.text
    resend_b = await ac.post("/api/v1/pos/sales", headers=cashier, json=pending)
    assert resend_b.json()["data"]["idempotent_replay"] is True
    assert await _count_sales(db_session, "cr-restore-a-0001") == 1
    assert await _count_sales(db_session, "cr-restore-b-0001") == 1


@pytest.mark.asyncio
async def test_policy_reports_server_grants_and_online_only_workflows(client):
    ac, _seed = client
    cashier = await _cashier(ac)
    r = await ac.get("/api/v1/pos/offline-policy", headers=cashier)
    data = r.json()["data"]
    assert data["grant_issuer"] == "server"
    assert data["offline_complete_claimed"] is False
    assert "max_sync_retries" not in data
    assert OFFLINE_COMPLETE_MISSING in data["limitations"]
    assert "platform_admin" in data["not_offline"]
    assert set(data["offline_tenders"]) == {"bank_transfer", "card", "cash", "credit", "mobile_money"}


@pytest.mark.asyncio
async def test_reservation_of_device_not_seen_for_hours_stops_blocking(client, db_session):
    """A browser or phone that stopped checking in no longer holds stock back from other tills."""
    ac, seed = client
    admin = await _super(ac, seed)
    store_id = await _store_with_stock(ac, db_session, seed, admin, qty=10, code="OFFST")
    cashier = await _cashier(ac)
    a = await _authorize(ac, cashier, "dev-stale-aaaa1", store_id)
    assert {x["product_id"]: x["allocated_qty"] for x in a["allocations"]}[seed["p1"].id] == 5

    # Device A was seen just now: B only gets half of what A left free.
    b = await _authorize(ac, cashier, "dev-stale-bbbb1", store_id)
    assert {x["product_id"]: x["allocated_qty"] for x in b["allocations"]}[seed["p1"].id] == 2

    # A stops checking in (abandoned browser). After the stale window its 5 units are free again.
    dev_a = (
        await db_session.execute(select(m.PosDevice).where(m.PosDevice.device_id == "dev-stale-aaaa1"))
    ).scalar_one()
    dev_a.last_seen_at = datetime.utcnow() - timedelta(hours=5)
    await db_session.commit()
    c = await _authorize(ac, cashier, "dev-stale-cccc1", store_id)
    # Free = 10 on hand - 2 held by B (A no longer counts) = 8; half of that is 4.
    assert {x["product_id"]: x["allocated_qty"] for x in c["allocations"]}[seed["p1"].id] == 4
