"""Pharmacy catalog dosage/Rx-only plus simple prescriptions (not a HIS)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, set_tenant_industry


@pytest.mark.asyncio
async def test_pharmacy_product_dosage_rx_and_prescription_path(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=admin,
        json={"dosage_instructions": "1 tablet twice daily after meals", "rx_only": True},
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["dosage_instructions"] == "1 tablet twice daily after meals"
    assert pdata["rx_only"] is True

    listed = await ac.get("/api/v1/products?rx_only=true", headers=admin)
    assert listed.status_code == 200, listed.text
    rx_rows = listed.json()["data"]
    assert any(row["id"] == product_id for row in rx_rows)

    rx_catalog = await ac.get("/api/v1/pharmacy/rx-products", headers=admin)
    assert rx_catalog.status_code == 200, rx_catalog.text
    assert any(row["id"] == product_id for row in rx_catalog.json()["data"])

    created = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "prescriber_name": "Dr Jane",
            "notes": "Recorded at counter",
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    rx = created.json()["data"]
    assert rx["rx_number"].startswith("RX-")
    assert rx["status"] == "received"
    assert rx["customer_id"] == seed["party1"].id
    assert rx["items"][0]["dosage_text"] == "1 tablet twice daily after meals"
    rx_id = rx["id"]

    listed_rx = await ac.get("/api/v1/pharmacy/prescriptions", headers=cashier)
    assert listed_rx.status_code == 200, listed_rx.text
    assert any(row["id"] == rx_id for row in listed_rx.json()["data"])

    denied_write = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=cashier,
        json={"items": [{"product_id": product_id, "quantity": 1}]},
    )
    assert denied_write.status_code == 403

    got = await ac.get(f"/api/v1/pharmacy/prescriptions/{rx_id}", headers=admin)
    assert got.status_code == 200
    assert got.json()["data"]["id"] == rx_id

    reviewed = await ac.patch(
        f"/api/v1/pharmacy/prescriptions/{rx_id}",
        headers=admin,
        json={"status": "review"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["status"] == "review"

    approved = await ac.patch(
        f"/api/v1/pharmacy/prescriptions/{rx_id}",
        headers=admin,
        json={"status": "approved"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200
    ids = {row["id"] for row in dash.json()["data"]["industry_features"]}
    hrefs = {row["href"] for row in dash.json()["data"]["industry_features"]}
    assert "rx_products" in ids
    assert "prescriptions" in ids
    assert "/prescriptions" in hrefs
    assert "/inventory?tab=products&rx=1" in hrefs
    queue = dash.json()["data"]["rx_queue"]
    assert queue["open"] >= 1
    assert queue["approved"] >= 1
    assert dash.json()["data"]["gross_profit_7d"] is not None

    cancelled = await ac.patch(
        f"/api/v1/pharmacy/prescriptions/{rx_id}",
        headers=admin,
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_prescriptions_pharmacy_only_and_tenant_isolated(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "mart")
    mart_admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/pharmacy/prescriptions", headers=mart_admin)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 1, "dosage_text": "5ml at night"}]},
    )
    assert created.status_code == 200, created.text
    rx_id = created.json()["data"]["id"]

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    other = await ac.get("/api/v1/pharmacy/prescriptions", headers=beta)
    assert other.status_code == 403

    await set_tenant_industry(db_session, seed["t2"], "pharmacy")
    beta_pharm = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    listed = await ac.get("/api/v1/pharmacy/prescriptions", headers=beta_pharm)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"] == []

    missing = await ac.get(f"/api/v1/pharmacy/prescriptions/{rx_id}", headers=beta_pharm)
    assert missing.status_code == 404

    await set_tenant_industry(db_session, seed["t1"], "mart")
    mart_again = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    holds = await ac.get("/api/v1/pharmacy/batch-holds", headers=mart_again)
    assert holds.status_code == 403


@pytest.mark.asyncio
async def test_legacy_voided_alias_cancels_received(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 1}]},
    )
    assert created.status_code == 200, created.text
    rx_id = created.json()["data"]["id"]
    voided = await ac.patch(
        f"/api/v1/pharmacy/prescriptions/{rx_id}",
        headers=admin,
        json={"status": "voided"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_pharmacy_pos_fefo_skips_expired_and_held_lots(client, db_session):
    from datetime import datetime, timedelta

    from app import models as m

    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    product = seed["p1"]
    product_id = product.id
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.tracks_batches = True
    expired = m.ProductBatch(
        tenant_id=seed["t1"].id,
        product_id=product.id,
        batch_number="EXP-1",
        quantity=8,
        expiry_date=datetime.utcnow() - timedelta(days=2),
    )
    fresh = m.ProductBatch(
        tenant_id=seed["t1"].id,
        product_id=product.id,
        batch_number="FRESH-1",
        quantity=8,
        expiry_date=datetime.utcnow() + timedelta(days=40),
    )
    db_session.add_all([expired, fresh])
    await db_session.commit()
    expired_id = expired.id
    fresh_id = fresh.id

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0},
        headers=cashier,
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 2}],
        },
        headers=cashier,
    )
    assert sale.status_code == 200, sale.text
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    lots = await ac.get(f"/api/v1/products/{product_id}/batches", headers=admin)
    assert lots.status_code == 200, lots.text
    by_id = {row["id"]: row for row in lots.json()["data"]}
    assert float(by_id[fresh_id]["quantity"]) == pytest.approx(6)
    assert float(by_id[expired_id]["quantity"]) == pytest.approx(8)

    search = await ac.get("/api/v1/pos/products/search?q=a", headers=cashier)
    assert search.status_code == 200, search.text
    hit = next(r for r in search.json()["data"] if r["product_id"] == product_id)
    assert hit.get("nearest_expiry_date")
    assert "rx_only" in hit

    held = await ac.post(
        "/api/v1/pharmacy/batch-holds",
        headers=admin,
        json={
            "batch_id": fresh_id,
            "hold_type": "quarantine",
            "reason": "Damaged carton held at counter",
        },
    )
    assert held.status_code == 200, held.text
    blocked = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=cashier,
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") in {"NO_SALEABLE_BATCH", "BATCH_ON_HOLD", "INSUFFICIENT_BATCH_STOCK"}

    retail_denied = await ac.get("/api/v1/pharmacy/batch-holds", headers=cashier)
    # cashier on pharmacy tenant can read inventory
    assert retail_denied.status_code in {200, 403}


@pytest.mark.asyncio
async def test_pharmacy_partial_dispense_and_pos_rx_gate(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 10
    await db_session.commit()
    patched = await ac.patch(
        f"/api/v1/products/{product.id}",
        headers=admin,
        json={"rx_only": True},
    )
    assert patched.status_code == 200, patched.text

    created = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=admin,
        json={"items": [{"product_id": product.id, "quantity": 4}]},
    )
    assert created.status_code == 200, created.text
    rx_id = created.json()["data"]["id"]
    await ac.patch(
        f"/api/v1/pharmacy/prescriptions/{rx_id}",
        headers=admin,
        json={"status": "approved"},
    )

    partial = await ac.post(
        f"/api/v1/pharmacy/prescriptions/{rx_id}/dispense",
        headers=admin,
        json={"items": [{"product_id": product.id, "quantity": 1}]},
    )
    assert partial.status_code == 200, partial.text
    pdata = partial.json()["data"]
    assert pdata["status"] == "partially_dispensed"
    assert pdata["items"][0]["qty_dispensed"] == 1
    assert pdata["items"][0]["qty_remaining"] == 3

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0},
        headers=cashier,
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    blocked = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
        headers=cashier,
    )
    assert blocked.status_code == 409, blocked.text
    assert (blocked.json().get("detail") or {}).get("code") == "RX_REQUIRED"

    sold = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "prescription_id": rx_id,
            "items": [{"product_id": product.id, "quantity": 2}],
        },
        headers=cashier,
    )
    assert sold.status_code == 200, sold.text
    filled = await ac.get(f"/api/v1/pharmacy/prescriptions/{rx_id}", headers=admin)
    assert filled.json()["data"]["items"][0]["qty_dispensed"] == 3
    assert filled.json()["data"]["status"] == "partially_dispensed"

