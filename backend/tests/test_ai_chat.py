"""Phase 4 / BR-21.1 rule-based AI ERP chat."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.rbac import permissions_for_role
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_top_selling_product_chat(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    now = datetime.utcnow()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-CHAT-TOP-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        created_at=now - timedelta(days=2),
        posted_at=now - timedelta(days=2),
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tenant_id,
            sales_invoice_id=inv.id,
            product_id=product.id,
            quantity=40,
            unit_price=2.5,
            line_total=100,
        )
    )
    await db_session.commit()

    r = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "What is my top selling product this month?"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["intent"] == "top_product"
    assert data["method"] == "rules_v1"
    assert product.name in data["answer"]
    assert data["data"]["product_id"] == product.id
    assert "Beta" not in data["answer"]


@pytest.mark.asyncio
async def test_create_draft_po_via_chat(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    supplier = m.Party(
        tenant_id=tenant_id,
        name="Alpha Supplier",
        kind="supplier",
        status="active",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.commit()

    r = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Create a purchase order for 50 units of Alpha Widget"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["intent"] == "create_po"
    assert data["data"].get("purchase_order_id")
    assert "draft purchase order" in data["answer"].lower() or "Created draft" in data["answer"]

    po = (
        await db_session.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.id == data["data"]["purchase_order_id"],
                m.PurchaseOrder.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    assert po.status == "draft"
    assert float(po.total_amount) >= 0


@pytest.mark.asyncio
async def test_create_po_denied_without_purchasing_write(client, db_session):
    """Sales officer has ai:read but not purchasing:write."""
    ac, seed = client
    sales = m.User(
        tenant_id=seed["t1"].id,
        email="sales@alpha.example.com",
        full_name="Alpha Sales",
        password_hash=seed["mgr1"].password_hash,
        role="sales_officer",
        email_verified=True,
        permissions=permissions_for_role("sales_officer"),
        totp_enabled=False,
    )
    db_session.add(sales)
    db_session.add(
        m.Party(
            tenant_id=seed["t1"].id,
            name="Alpha Supplier 2",
            kind="supplier",
            status="active",
        )
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="sales@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Create a purchase order for 10 units of Alpha Widget"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["intent"] == "create_po"
    assert data["data"].get("denied") is True
    assert "purchasing write" in data["answer"].lower()


@pytest.mark.asyncio
async def test_chat_history_persisted_and_user_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    first = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "help"},
    )
    assert first.status_code == 200, first.text

    hist = await ac.get("/api/v1/ai/chat/history", headers=headers)
    assert hist.status_code == 200, hist.text
    items = hist.json()["data"]["items"]
    assert len(items) >= 1
    assert items[0]["message"] == "help"
    assert items[0]["answer"]
    assert "Beta" not in items[0]["answer"]

    # Beta tenant user cannot see alpha history even with same message pattern
    beta_headers = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    # cashier has no ai permission
    denied = await ac.get("/api/v1/ai/chat/history", headers=beta_headers)
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client):
    ac, _seed = client
    headers = await _mgr(ac)
    r = await ac.post("/api/v1/ai/chat", headers=headers, json={"message": "   "})
    assert r.status_code == 400
