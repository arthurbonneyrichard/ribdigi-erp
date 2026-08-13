"""Credit limit override with credit:approve (BR-11.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.credit import enforce_customer_credit_limit, claims_may_override_credit
from app.rbac import permissions_for_role
from fastapi import HTTPException
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_enforce_blocks_without_override():
    party = m.Party(name="A", kind="customer", credit_limit=100, balance=80)
    party.id = "c1"
    with pytest.raises(HTTPException) as ei:
        enforce_customer_credit_limit(party, amount=30)
    assert ei.value.status_code == 409
    assert ei.value.detail["code"] == "CREDIT_LIMIT_EXCEEDED"
    assert abs(float(ei.value.detail["over_by"]) - 10) < 0.01


def test_enforce_forbidden_without_approve():
    party = m.Party(name="A", kind="customer", credit_limit=100, balance=80)
    party.id = "c1"
    with pytest.raises(HTTPException) as ei:
        enforce_customer_credit_limit(
            party, amount=30, override=True, override_allowed=False
        )
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "CREDIT_OVERRIDE_FORBIDDEN"


def test_enforce_override_returns_audit_payload():
    party = m.Party(name="A", kind="customer", credit_limit=100, balance=80)
    party.id = "c1"
    info = enforce_customer_credit_limit(
        party,
        amount=30,
        override=True,
        override_allowed=True,
        override_reason="VIP exception",
    )
    assert info is not None
    assert info["reason"] == "VIP exception"
    assert abs(float(info["over_by"]) - 10) < 0.01


def test_claims_may_override_credit_roles():
    assert claims_may_override_credit({"role": "store_manager", "permissions": permissions_for_role("store_manager")})
    assert claims_may_override_credit({"role": "accountant", "permissions": permissions_for_role("accountant")})
    assert not claims_may_override_credit({"role": "sales_officer", "permissions": permissions_for_role("sales_officer")})
    assert not claims_may_override_credit({"role": "cashier", "permissions": permissions_for_role("cashier")})


@pytest.mark.asyncio
async def test_invoice_post_blocks_then_allows_override(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 50},
    )
    assert stock.status_code == 200, stock.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Limit Buyer", "credit_limit": 100},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    # sales_officer: sales write, no credit:approve (own record scope)
    so = m.User(
        tenant_id=seed["t1"].id,
        email="sales@alpha.example.com",
        full_name="Sales Officer",
        password_hash=seed["u1"].password_hash,
        role="sales_officer",
        email_verified=True,
        permissions=permissions_for_role("sales_officer"),
        totp_enabled=False,
    )
    db_session.add(so)
    await db_session.commit()
    so_headers = await auth_headers(ac, email="sales@alpha.example.com", tenant_slug="alpha")

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=so_headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 130}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]

    blocked = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=so_headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "CREDIT_LIMIT_EXCEEDED"

    forbidden = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=so_headers,
        json={"override_credit_limit": True, "override_reason": "please"},
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["detail"]["code"] == "CREDIT_OVERRIDE_FORBIDDEN"

    mgr_headers = await _mgr(ac)
    ok = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=mgr_headers,
        json={"override_credit_limit": True, "override_reason": "Approved by manager"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["credit_limit_overridden"] is True

    party = (
        await db_session.execute(select(m.Party).where(m.Party.id == customer_id))
    ).scalar_one()
    assert abs(float(party.balance) - 130) < 0.01

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "credit_limit_override",
                m.AuditLog.entity_id == customer_id,
            )
        )
    ).scalars().all()
    assert len(audits) >= 1
    assert audits[-1].details.get("reason") == "Approved by manager"


@pytest.mark.asyncio
async def test_legacy_sale_tx_credit_override(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    # party1 limit 100, balance 0 — sell 150 with override
    r = await ac.post(
        "/api/v1/sales",
        headers=headers,
        json={
            "party_id": seed["party1"].id,
            "total": 150,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
            "override_credit_limit": True,
            "override_reason": "legacy override",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["credit_limit_overridden"] is True

    blocked = await ac.post(
        "/api/v1/sales",
        headers=headers,
        json={
            "party_id": seed["party1"].id,
            "total": 1,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    # balance already 150 > limit 100; even +1 is over — should 409 without override
    assert blocked.status_code == 409
