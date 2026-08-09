"""Stage 3 C1: credit-limit override with reason + audit (BR-11.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import sales as sales_svc
from app.rbac import has_permission, permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _draft_invoice(db, *, tenant_id, user_id, customer_id, product_id, total=150.0):
    inv = await sales_svc.create_sales_invoice(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=customer_id,
        items=[
            {
                "product_id": product_id,
                "quantity": 1,
                "unit_price": total,
                "tax_rate": 0,
                "discount": 0,
            }
        ],
        notes="C1 credit test",
    )
    await db.commit()
    return inv


@pytest.mark.asyncio
async def test_invoice_post_blocks_then_overrides_with_audit(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    customer.credit_limit = 100
    customer.balance = 0
    seed["p1"].selling_price = 150
    seed["p1"].stock_qty = 100
    await db_session.commit()

    inv = await _draft_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        customer_id=customer.id,
        product_id=seed["p1"].id,
        total=150,
    )

    blocked = await ac.post(
        f"/api/v1/sales/invoices/{inv.id}/post",
        headers=headers,
        json={},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "CREDIT_LIMIT_EXCEEDED"

    missing_reason = await ac.post(
        f"/api/v1/sales/invoices/{inv.id}/post",
        headers=headers,
        json={"credit_limit_override": True, "credit_override_reason": "x"},
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"]["code"] == "CREDIT_OVERRIDE_REASON_REQUIRED"

    ok = await ac.post(
        f"/api/v1/sales/invoices/{inv.id}/post",
        headers=headers,
        json={
            "credit_limit_override": True,
            "credit_override_reason": "VIP exception approved by finance",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["status"] == "posted"
    assert data["credit_limit_overridden"] is True
    assert "VIP exception" in (data["credit_override_reason"] or "")

    events = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.action == "credit_limit_override",
                m.AuditLog.entity_id == inv.id,
            )
        )
    ).scalars().all()
    assert len(events) >= 1
    assert events[0].details.get("reason")


@pytest.mark.asyncio
async def test_override_requires_credit_approve_role(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    # sales_officer has credit:write but not approve
    officer = m.User(
        tenant_id=tenant_id,
        email="sales@alpha.example.com",
        full_name="Sales Officer",
        password_hash=hash_password("SecurePass123!"),
        role="sales_officer",
        email_verified=True,
        permissions=permissions_for_role("sales_officer"),
        totp_enabled=False,
    )
    db_session.add(officer)
    customer = seed["party1"]
    customer.credit_limit = 50
    customer.balance = 0
    seed["p1"].stock_qty = 100
    await db_session.commit()

    inv = await _draft_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=officer.id,
        customer_id=customer.id,
        product_id=seed["p1"].id,
        total=80,
    )

    headers = await auth_headers(ac, email="sales@alpha.example.com", tenant_slug="alpha")
    forbidden = await ac.post(
        f"/api/v1/sales/invoices/{inv.id}/post",
        headers=headers,
        json={
            "credit_limit_override": True,
            "credit_override_reason": "Trying without approve right",
        },
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["detail"]["code"] == "CREDIT_OVERRIDE_FORBIDDEN"


@pytest.mark.asyncio
async def test_pos_credit_override_and_cashier_denied(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    customer.credit_limit = 20
    customer.balance = 0
    customer.party_type = "registered"
    seed["p1"].selling_price = 50
    seed["p1"].tax_rate_id = None
    seed["p1"].stock_qty = 100
    await db_session.commit()

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200
    sid = opened.json()["data"]["session_id"]

    blocked = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": sid,
            "party_id": customer.id,
            "payment_method": "credit",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "CREDIT_LIMIT_EXCEEDED"

    denied = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": sid,
            "party_id": customer.id,
            "payment_method": "credit",
            "credit_limit_override": True,
            "credit_override_reason": "Cashier should not override",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "CREDIT_OVERRIDE_FORBIDDEN"

    # Manager with credit:approve via store_manager — but seed mgr lacks 2FA? store_manager doesn't require 2FA
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    # Manager needs open session — open for manager
    opened_m = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=mgr,
        json={"opening_cash": 50},
    )
    assert opened_m.status_code == 200, opened_m.text
    sid_m = opened_m.json()["data"]["session_id"]
    ok = await ac.post(
        "/api/v1/pos/sales",
        headers=mgr,
        json={
            "session_id": sid_m,
            "party_id": customer.id,
            "payment_method": "credit",
            "credit_limit_override": True,
            "credit_override_reason": "Store manager VIP approval",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["credit_limit_overridden"] is True
    await db_session.refresh(customer)
    assert float(customer.balance or 0) == 50


def test_credit_approve_permission_catalog():
    assert has_permission("store_manager", "credit", "approve")
    assert has_permission("accountant", "credit", "approve")
    assert not has_permission("sales_officer", "credit", "approve")
    assert not has_permission("cashier", "credit", "approve")
