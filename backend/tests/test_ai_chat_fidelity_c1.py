"""Stage 20 C1: AI ERP chat fidelity (BR-21.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.rbac import permissions_for_role
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_nl_query_top_product_role_scoped(client, db_session):
    """BR-21.1: NL Q&A + role-aware sales read."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    now = datetime.utcnow()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-C1-TOP-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=200,
        tax_amount=0,
        total_amount=200,
        created_at=now - timedelta(days=1),
        posted_at=now - timedelta(days=1),
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tenant_id,
            sales_invoice_id=inv.id,
            product_id=product.id,
            quantity=80,
            unit_price=2.5,
            line_total=200,
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

    # User with ai:read only (no sales/dashboard) → denied for top product
    ai_only = m.User(
        tenant_id=tenant_id,
        email="ai-only-c1@alpha.example.com",
        full_name="AI Only C1",
        password_hash=seed["mgr1"].password_hash,
        role="sales_officer",
        email_verified=True,
        permissions={"ai": ["read"], "security": ["read", "write"]},
        totp_enabled=False,
    )
    db_session.add(ai_only)
    await db_session.commit()
    ai_h = await auth_headers(ac, email="ai-only-c1@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        "/api/v1/ai/chat",
        headers=ai_h,
        json={"message": "What is my top selling product this month?"},
    )
    assert denied.status_code == 200, denied.text
    assert "permission" in denied.json()["data"]["answer"].lower()

    # Cashier has no ai module → API gate 403
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    blocked = await ac.post(
        "/api/v1/ai/chat",
        headers=cash,
        json={"message": "help"},
    )
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_safe_create_po_command_and_deny(client, db_session):
    """BR-21.1: command path creates draft PO only with purchasing write."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    db_session.add(
        m.Party(
            tenant_id=tenant_id,
            name="C1 Supplier",
            kind="supplier",
            status="active",
            credit_limit=0,
        )
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Create a purchase order for 50 units of Alpha Widget"},
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["intent"] == "create_po"
    po_id = body["data"].get("purchase_order_id")
    assert po_id
    po = (
        await db_session.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.id == po_id,
                m.PurchaseOrder.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    assert po.status == "draft"

    sales = m.User(
        tenant_id=tenant_id,
        email="sales-c1@alpha.example.com",
        full_name="Sales C1",
        password_hash=seed["mgr1"].password_hash,
        role="sales_officer",
        email_verified=True,
        permissions=permissions_for_role("sales_officer"),
        totp_enabled=False,
    )
    db_session.add(sales)
    await db_session.commit()
    sales_h = await auth_headers(ac, email="sales-c1@alpha.example.com", tenant_slug="alpha")
    refused = await ac.post(
        "/api/v1/ai/chat",
        headers=sales_h,
        json={"message": "Create a purchase order for 10 units of Alpha Widget"},
    )
    assert refused.status_code == 200, refused.text
    assert refused.json()["data"]["data"].get("denied") is True
    assert "purchasing write" in refused.json()["data"]["answer"].lower()


@pytest.mark.asyncio
async def test_chat_history_persistence(client):
    """BR-21.1: chat history persisted per user."""
    ac, _seed = client
    headers = await _mgr(ac)

    ask = await ac.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "help"},
    )
    assert ask.status_code == 200, ask.text
    assert ask.json()["data"]["intent"] == "help"

    hist = await ac.get("/api/v1/ai/chat/history", headers=headers)
    assert hist.status_code == 200, hist.text
    items = hist.json()["data"]["items"]
    assert any(i.get("message") == "help" and i.get("answer") for i in items)


def test_br_21_1_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s211 = br.split("#### BR-21.1 AI ERP Chat Assistant")[1].split("#### BR-21.2")[0]
    assert "[x] Accept natural language queries" in s211
    assert "[x] Execute commands via chat" in s211
    assert "[x] Context-aware responses based on user role and permissions" in s211
    assert "[x] Chat history persistence" in s211
    assert "Stage 20 C1" in s211
    assert "test_ai_chat_fidelity_c1.py" in s211

    plan = (ROOT / "docs" / "STAGE_20_PLAN.md").read_text(encoding="utf-8")
    c1_line = [ln for ln in plan.splitlines() if "| **C1**" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_ai_chat_fidelity_c1.py" in plan
