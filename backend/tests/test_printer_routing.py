"""Tenant printer routing, isolation, and idempotent reprint (no physical printers)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import models as m
from app import printers as printers_svc
from tests.conftest import auth_headers, set_tenant_industry


@pytest.mark.asyncio
async def test_cashier_cannot_manage_printers(client):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/printers",
        headers=cashier,
        json={
            "name": "Till receipt",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_printers_are_tenant_isolated(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Alpha receipt",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert created.status_code == 200, created.text
    printer_id = created.json()["data"]["id"]

    cross = dict(admin)
    cross["X-Tenant-ID"] = seed["t2"].id
    listed = await ac.get("/api/v1/printers", headers=cross)
    assert listed.status_code == 403

    listed_ok = await ac.get("/api/v1/printers", headers=admin)
    assert listed_ok.status_code == 200
    ids = {row["id"] for row in listed_ok.json()["data"]}
    assert printer_id in ids


@pytest.mark.asyncio
async def test_printer_test_print_fits_source_id(client):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Ready till",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["is_enabled"] is True
    assert body["status"] == "online"
    tested = await ac.post(f"/api/v1/printers/{body['id']}/test", headers=admin, json={})
    assert tested.status_code == 200, tested.text
    job = tested.json()["data"]
    assert job["status"] == "browser_pending"
    assert job["source_id"] and len(job["source_id"]) <= 36
    assert "The server could not complete this request." not in tested.text


@pytest.mark.asyncio
async def test_network_printer_rejects_public_host(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Public host",
            "connection_type": "network",
            "purposes": ["customer_receipt"],
            "host": "8.8.8.8",
            "port": 9100,
        },
    )
    assert r.status_code == 400


def test_network_receipt_sends_escpos(monkeypatch):
    sent: dict = {}

    class _Sock:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendall(self, data):
            sent["data"] = data

    def _connect(addr, timeout):
        sent["addr"] = addr
        sent["timeout"] = timeout
        return _Sock()

    monkeypatch.setattr(printers_svc.socket, "create_connection", _connect)
    printers_svc.send_network_receipt("192.168.1.130", 9100, "Demo Mart\n2 Bottled Water        20.00\n")
    assert sent["addr"] == ("192.168.1.130", 9100)
    assert sent["data"].startswith(b"\x1b\x40\x1b\x61\x00")
    assert b"Demo Mart" in sent["data"]
    assert b"Bottled Water" in sent["data"]
    assert sent["data"].endswith(b"\x1d\x56\x00")


def test_validate_network_host_allows_rfc1918():
    assert printers_svc.validate_network_host("192.168.1.50") == "192.168.1.50"
    with pytest.raises(HTTPException):
        printers_svc.validate_network_host("169.254.169.254")


@pytest.mark.asyncio
async def test_routing_split_and_queued_is_not_printed(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    kitchen_p = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Kitchen",
            "connection_type": "print_agent",
            "purposes": ["kitchen"],
            "agent_id": None,
        },
    )
    # print_agent without agent_id should 400 — use browser_dialog for simulated queue
    assert kitchen_p.status_code == 400
    kitchen_p = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen"],
        },
    )
    bar_p = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Bar",
            "connection_type": "browser_dialog",
            "purposes": ["bar"],
        },
    )
    receipt_p = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Receipt",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert kitchen_p.status_code == 200, kitchen_p.text
    assert bar_p.status_code == 200, bar_p.text
    assert receipt_p.status_code == 200, receipt_p.text

    food = m.Product(
        tenant_id=seed["t1"].id,
        name="Jollof",
        sku="FOOD-1",
        selling_price=20,
        stock_qty=10,
        prep_station="kitchen",
    )
    drink = m.Product(
        tenant_id=seed["t1"].id,
        name="Sobolo",
        sku="DRINK-1",
        selling_price=8,
        stock_qty=10,
        prep_station="bar",
    )
    db_session.add_all([food, drink])
    await db_session.flush()
    tx = m.Transaction(
        tenant_id=seed["t1"].id,
        tx_type="pos_sale",
        reference="POS-TEST-1",
        subtotal=28,
        tax=0,
        total=28,
        status="completed",
        payload={
            "items": [
                {"product_id": food.id, "name": "Jollof", "quantity": 1, "unit_price": 20},
                {"product_id": drink.id, "name": "Sobolo", "quantity": 1, "unit_price": 8},
            ],
            "payment_method": "cash",
            "payments": [{"payment_method": "cash", "amount": 28}],
        },
        created_at=datetime.utcnow(),
    )
    db_session.add(tx)
    await db_session.flush()
    jobs = await printers_svc.enqueue_pos_sale_prints(
        db_session,
        tenant_id=seed["t1"].id,
        tx=tx,
        user_id=seed["admin1"].id,
        store_id=None,
        tenant=seed["t1"],
        store=None,
    )
    await db_session.commit()
    purposes = sorted({j.purpose for j in jobs})
    assert purposes == ["bar", "customer_receipt", "kitchen"]
    assert all(j.status == "browser_pending" for j in jobs)
    assert all(j.status != "printed" for j in jobs)
    kitchen_job = next(j for j in jobs if j.purpose == "kitchen")
    kitchen_text = (kitchen_job.payload or {}).get("text", "").lower()
    assert "cash" not in kitchen_text
    assert kitchen_job.payload.get("payments_included") is False
    assert tx.reference == "POS-TEST-1"

    sale_count = (
        await db_session.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == seed["t1"].id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalars().all()
    assert len(sale_count) == 1

    reprints = await printers_svc.reprint_source(
        db_session,
        tenant_id=seed["t1"].id,
        source_type="pos_sale",
        source_id=tx.id,
        purposes=["customer_receipt"],
        user_id=seed["admin1"].id,
    )
    await db_session.commit()
    assert reprints
    assert reprints[0].id != kitchen_job.id
    assert reprints[0].source_id == tx.id
    sale_count2 = (
        await db_session.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == seed["t1"].id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalars().all()
    assert len(sale_count2) == 1

    retried = await printers_svc.retry_job(
        db_session,
        tenant_id=seed["t1"].id,
        job_id=kitchen_job.id,
        user_id=seed["admin1"].id,
    )
    await db_session.commit()
    assert retried.source_id == tx.id
    assert retried.status == "browser_pending"
    sale_count3 = (
        await db_session.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == seed["t1"].id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalars().all()
    assert len(sale_count3) == 1


@pytest.mark.asyncio
async def test_enqueue_same_sale_is_idempotent(client, db_session):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Front till",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    tx = m.Transaction(
        tenant_id=seed["t1"].id,
        tx_type="pos_sale",
        reference="POS-IDEM-1",
        subtotal=2,
        tax=0,
        total=2,
        status="completed",
        payload={"items": [], "payment_method": "cash"},
        created_at=datetime.utcnow(),
    )
    db_session.add(tx)
    await db_session.flush()
    first = await printers_svc.enqueue_pos_sale_prints(
        db_session,
        tenant_id=seed["t1"].id,
        tx=tx,
        user_id=seed["admin1"].id,
        store_id=None,
        tenant=seed["t1"],
        store=None,
    )
    second = await printers_svc.enqueue_pos_sale_prints(
        db_session,
        tenant_id=seed["t1"].id,
        tx=tx,
        user_id=seed["admin1"].id,
        store_id=None,
        tenant=seed["t1"],
        store=None,
    )
    await db_session.commit()
    assert [j.id for j in first] == [j.id for j in second]


def test_purposes_for_industry_hides_kitchen_outside_restaurant():
    general = ["barcode", "customer_receipt", "invoice"]
    for industry in ("retail", "hotel", "pharmacy", "bakery", "mart", "fmcg", None):
        assert printers_svc.purposes_for_industry(industry) == general
        assert "kitchen" not in printers_svc.purposes_for_industry(industry)
        assert "bar" not in printers_svc.purposes_for_industry(industry)
    restaurant = printers_svc.purposes_for_industry("restaurant")
    assert restaurant == ["bar", "barcode", "customer_receipt", "invoice", "kitchen"]
    assert printers_svc.purposes_for_industry("food_service") == restaurant
    assert printers_svc.visible_purposes_for_industry(["kitchen", "customer_receipt"], "retail") == [
        "customer_receipt"
    ]
    assert printers_svc.visible_purposes_for_industry(["kitchen"], "retail") == []
    assert printers_svc.visible_purposes_for_industry(["kitchen"], "restaurant") == ["kitchen"]


@pytest.mark.asyncio
async def test_retail_capabilities_omit_kitchen_and_api_rejects_kitchen(client, db_session):
    ac, seed = client
    assert (seed["t1"].industry or "").lower() == "retail"
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    caps = await ac.get("/api/v1/printers/capabilities", headers=admin)
    assert caps.status_code == 200, caps.text
    data = caps.json()["data"]
    assert data["industry"] == "retail"
    assert "kitchen" not in data["purposes"]
    assert "bar" not in data["purposes"]
    assert set(data["purposes"]) == {"barcode", "customer_receipt", "invoice"}
    assert data["industry_specific_purposes"] == []
    assert data["prep_stations"] == []

    rejected = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Retail kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen"],
        },
    )
    assert rejected.status_code == 400, rejected.text
    assert "kitchen" in rejected.text.lower()

    ok = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Retail receipt",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt", "invoice", "barcode"],
        },
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_hotel_does_not_invent_restaurant_kitchen(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    caps = await ac.get("/api/v1/printers/capabilities", headers=admin)
    assert caps.status_code == 200, caps.text
    data = caps.json()["data"]
    assert data["industry"] == "hotel"
    assert "kitchen" not in data["purposes"]
    assert "bar" not in data["purposes"]
    rejected = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Hotel kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen"],
        },
    )
    assert rejected.status_code == 400, rejected.text


@pytest.mark.asyncio
async def test_restaurant_capabilities_include_kitchen_bar(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    caps = await ac.get("/api/v1/printers/capabilities", headers=admin)
    assert caps.status_code == 200, caps.text
    data = caps.json()["data"]
    assert data["industry"] == "restaurant"
    assert set(data["purposes"]) >= {"customer_receipt", "invoice", "barcode", "kitchen", "bar"}
    created = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Pass kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen"],
        },
    )
    assert created.status_code == 200, created.text


@pytest.mark.asyncio
async def test_retail_routing_ignores_leftover_kitchen_printer(client, db_session):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    receipt = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Front till",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert receipt.status_code == 200, receipt.text
    leftover = m.Printer(
        tenant_id=seed["t1"].id,
        name="Orphan kitchen",
        connection_type="browser_dialog",
        paper="80mm",
        purposes=["kitchen"],
        copies=1,
        is_enabled=True,
    )
    food = m.Product(
        tenant_id=seed["t1"].id,
        name="Jollof leftover",
        sku="FOOD-LEFT-1",
        selling_price=20,
        stock_qty=10,
        prep_station="kitchen",
    )
    db_session.add_all([leftover, food])
    await db_session.flush()
    tx = m.Transaction(
        tenant_id=seed["t1"].id,
        tx_type="pos_sale",
        reference="POS-RETAIL-KITCHEN-1",
        subtotal=20,
        tax=0,
        total=20,
        status="completed",
        payload={
            "items": [
                {"product_id": food.id, "name": "Jollof leftover", "quantity": 1, "unit_price": 20},
            ],
            "payment_method": "cash",
        },
        created_at=datetime.utcnow(),
    )
    db_session.add(tx)
    await db_session.flush()
    jobs = await printers_svc.enqueue_pos_sale_prints(
        db_session,
        tenant_id=seed["t1"].id,
        tx=tx,
        user_id=seed["admin1"].id,
        store_id=None,
        tenant=seed["t1"],
        store=None,
    )
    await db_session.commit()
    purposes = {j.purpose for j in jobs}
    assert "kitchen" not in purposes
    assert "bar" not in purposes
    assert purposes == {"customer_receipt"}

    listed = await ac.get("/api/v1/printers", headers=admin)
    assert listed.status_code == 200, listed.text
    names = {row["name"] for row in listed.json()["data"]}
    assert "Front till" in names
    assert "Orphan kitchen" not in names
    leftover_row = await db_session.get(m.Printer, leftover.id)
    assert leftover_row is not None
    assert leftover_row.purposes == ["kitchen"]


@pytest.mark.asyncio
async def test_industry_change_drops_kitchen_without_affecting_other_tenant(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    kitchen = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Alpha kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen"],
        },
    )
    receipt = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Alpha receipt",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert kitchen.status_code == 200, kitchen.text
    assert receipt.status_code == 200, receipt.text
    kitchen_id = kitchen.json()["data"]["id"]
    receipt_id = receipt.json()["data"]["id"]

    beta_kitchen = m.Printer(
        tenant_id=seed["t2"].id,
        name="Beta kitchen stays",
        connection_type="browser_dialog",
        paper="80mm",
        purposes=["kitchen"],
        copies=1,
        is_enabled=True,
    )
    db_session.add(beta_kitchen)
    await db_session.flush()

    from app import tenants as tenants_svc

    await tenants_svc.update_profile(db_session, seed["t1"], industry="retail")
    await db_session.commit()

    alpha_kitchen = await db_session.get(m.Printer, kitchen_id)
    alpha_receipt = await db_session.get(m.Printer, receipt_id)
    await db_session.refresh(beta_kitchen)
    assert alpha_kitchen is not None
    assert alpha_kitchen.purposes == []
    assert alpha_kitchen.is_enabled is False
    assert alpha_receipt is not None
    assert alpha_receipt.purposes == ["customer_receipt"]
    assert alpha_receipt.is_enabled is True
    assert beta_kitchen.purposes == ["kitchen"]
    assert beta_kitchen.is_enabled is True

    rejected = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "After change kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen"],
        },
    )
    assert rejected.status_code == 400, rejected.text



@pytest.mark.asyncio
async def test_retail_list_hides_kitchen_and_strips_mixed_leftover(client, db_session):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    receipt = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Retail till",
            "connection_type": "browser_dialog",
            "purposes": ["customer_receipt"],
        },
    )
    assert receipt.status_code == 200, receipt.text
    kitchen_only = m.Printer(
        tenant_id=seed["t1"].id,
        name="Hidden kitchen leftover",
        connection_type="browser_dialog",
        paper="80mm",
        purposes=["kitchen"],
        copies=1,
        is_enabled=False,
    )
    mixed = m.Printer(
        tenant_id=seed["t1"].id,
        name="Mixed leftover",
        connection_type="browser_dialog",
        paper="80mm",
        purposes=["kitchen", "customer_receipt"],
        copies=1,
        is_enabled=True,
    )
    other_tenant = m.Printer(
        tenant_id=seed["t2"].id,
        name="Beta kitchen stays",
        connection_type="browser_dialog",
        paper="80mm",
        purposes=["kitchen"],
        copies=1,
        is_enabled=True,
    )
    db_session.add_all([kitchen_only, mixed, other_tenant])
    await db_session.commit()

    listed = await ac.get("/api/v1/printers", headers=admin)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    by_name = {row["name"]: row for row in rows}
    assert "Retail till" in by_name
    assert "Hidden kitchen leftover" not in by_name
    assert "Beta kitchen stays" not in by_name
    assert "Mixed leftover" in by_name
    assert "kitchen" not in by_name["Mixed leftover"]["purposes"]
    assert "bar" not in by_name["Mixed leftover"]["purposes"]
    assert by_name["Mixed leftover"]["purposes"] == ["customer_receipt"]

    still_kitchen = await db_session.get(m.Printer, kitchen_only.id)
    still_other = await db_session.get(m.Printer, other_tenant.id)
    assert still_kitchen is not None and still_kitchen.purposes == ["kitchen"]
    assert still_other is not None and still_other.purposes == ["kitchen"]
    assert still_other.is_enabled is True


@pytest.mark.asyncio
async def test_restaurant_list_still_shows_kitchen(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/printers",
        headers=admin,
        json={
            "name": "Expo kitchen",
            "connection_type": "browser_dialog",
            "purposes": ["kitchen", "bar"],
        },
    )
    assert created.status_code == 200, created.text
    listed = await ac.get("/api/v1/printers", headers=admin)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(row["name"] == "Expo kitchen" for row in rows)
    kitchen_row = next(row for row in rows if row["name"] == "Expo kitchen")
    assert set(kitchen_row["purposes"]) == {"kitchen", "bar"}
