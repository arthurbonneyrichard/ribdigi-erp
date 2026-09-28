"""Tenant printer routing, isolation, and idempotent reprint (no physical printers)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import models as m
from app import printers as printers_svc
from tests.conftest import auth_headers


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


def test_validate_network_host_allows_rfc1918():
    assert printers_svc.validate_network_host("192.168.1.50") == "192.168.1.50"
    with pytest.raises(HTTPException):
        printers_svc.validate_network_host("169.254.169.254")


@pytest.mark.asyncio
async def test_routing_split_and_queued_is_not_printed(client, db_session):
    ac, seed = client
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
