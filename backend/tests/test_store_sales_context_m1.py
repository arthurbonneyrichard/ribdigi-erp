"""Stage 4 M1: store-specific sales API + tenant isolation (BR-13.1)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app import models as m
from app.stores import create_store
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_store_sales_summary_and_isolation(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id

    store_a = await create_store(
        db_session, tenant_id=tenant_id, code="SA1", name="Store A"
    )
    store_b = await create_store(
        db_session, tenant_id=tenant_id, code="SB1", name="Store B"
    )
    foreign = await create_store(
        db_session, tenant_id=seed["t2"].id, code="FX1", name="Foreign Store"
    )
    await db_session.flush()

    now = datetime.utcnow()
    inv_a = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SA-1",
        customer_id=seed["party1"].id,
        store_id=store_a.id,
        status="posted",
        subtotal=100,
        tax_amount=10,
        total_amount=110,
        posted_at=now,
    )
    inv_b = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SB-1",
        customer_id=seed["party1"].id,
        store_id=store_b.id,
        status="posted",
        subtotal=50,
        tax_amount=5,
        total_amount=55,
        posted_at=now,
    )
    session = m.PosSession(
        tenant_id=tenant_id,
        store_id=store_a.id,
        user_id=seed["mgr1"].id,
        session_number="SESS-SA-1",
        status="open",
        opening_cash=0,
    )
    db_session.add_all([inv_a, inv_b, session])
    await db_session.flush()
    pos = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-SA-1",
        session_id=session.id,
        subtotal=20,
        tax=2,
        total=22,
        status="completed",
    )
    db_session.add(pos)
    await db_session.commit()

    sales_a = await ac.get(f"/api/v1/stores/{store_a.id}/sales", headers=headers)
    assert sales_a.status_code == 200, sales_a.text
    data = sales_a.json()["data"]
    assert data["store"]["id"] == store_a.id
    assert data["summary"]["invoice_count"] == 1
    assert data["summary"]["pos_count"] == 1
    assert data["summary"]["sale_count"] == 2
    assert data["summary"]["revenue"] == pytest.approx(132.0)
    numbers = {r["number"] for r in data["recent"]}
    assert "INV-SA-1" in numbers
    assert "POS-SA-1" in numbers
    assert "INV-SB-1" not in numbers

    sales_b = await ac.get(f"/api/v1/stores/{store_b.id}/sales", headers=headers)
    assert sales_b.status_code == 200
    assert sales_b.json()["data"]["summary"]["invoice_count"] == 1
    assert sales_b.json()["data"]["summary"]["pos_count"] == 0
    assert sales_b.json()["data"]["summary"]["revenue"] == pytest.approx(55.0)

    missing = await ac.get(f"/api/v1/stores/{foreign.id}/sales", headers=headers)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200
    codes = {s["code"] for s in listed.json()["data"]}
    assert "SA1" in codes
    assert "FX1" not in codes


@pytest.mark.asyncio
async def test_store_sales_date_filter(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, code="SD1", name="Dated Store"
    )
    await db_session.flush()
    old = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-OLD-1",
        customer_id=seed["party1"].id,
        store_id=store.id,
        status="posted",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        posted_at=datetime(2020, 1, 15, 12, 0, 0),
    )
    recent = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-NEW-1",
        customer_id=seed["party1"].id,
        store_id=store.id,
        status="posted",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        posted_at=datetime(2026, 8, 1, 12, 0, 0),
    )
    db_session.add_all([old, recent])
    await db_session.commit()

    filtered = await ac.get(
        f"/api/v1/stores/{store.id}/sales",
        headers=headers,
        params={"from_date": "2026-01-01", "to_date": "2026-12-31"},
    )
    assert filtered.status_code == 200, filtered.text
    data = filtered.json()["data"]
    assert data["summary"]["invoice_count"] == 1
    assert data["summary"]["revenue"] == pytest.approx(40.0)
    assert data["recent"][0]["number"] == "INV-NEW-1"
