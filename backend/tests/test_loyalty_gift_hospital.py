"""Loyalty, gift cards, hospital visits, and checkout payment notices."""

from __future__ import annotations

from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException

from app import loyalty_gift as loyalty_gift_svc
from tests.conftest import auth_headers, set_tenant_industry


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_gift_card_and_loyalty_stay_in_tenant(db_session, seeded):
    card = await loyalty_gift_svc.issue_gift_card(
        db_session, tenant_id=seeded["t1"].id, user_id=None, amount=25
    )
    await db_session.commit()
    assert float(card.balance) == 25
    await loyalty_gift_svc.settle_pos_tenders(
        db_session,
        tenant_id=seeded["t1"].id,
        party_id=None,
        payments=[{"payment_method": "gift_card", "amount": 10, "reference": card.code}],
    )
    await db_session.refresh(card)
    assert float(card.balance) == 15
    with pytest.raises(HTTPException) as missing:
        await loyalty_gift_svc.get_gift_card(
            db_session, tenant_id="other-tenant", code=card.code
        )
    assert missing.value.status_code == 404

    party = await loyalty_gift_svc.adjust_loyalty(
        db_session, tenant_id=seeded["t1"].id, party_id=seeded["party1"].id, delta=8
    )
    assert float(party.loyalty_points) == 8
    await loyalty_gift_svc.settle_pos_tenders(
        db_session,
        tenant_id=seeded["t1"].id,
        party_id=party.id,
        payments=[{"payment_method": "loyalty", "amount": 3, "reference": None}],
    )
    await db_session.refresh(party)
    assert float(party.loyalty_points) == 5


@pytest.mark.asyncio
async def test_hospital_visits_are_industry_gated(client, db_session, seeded):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        "/api/v1/hospital/patients",
        headers=admin,
        json={"name": "Ada Patient"},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    await set_tenant_industry(db_session, seed["t1"], "hospital")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/hospital/patients",
        headers=admin,
        json={"name": "Ada Patient"},
    )
    assert created.status_code == 403, created.text
    assert created.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"
    assert "Ada Patient" not in created.text
    visit = await ac.post(
        "/api/v1/hospital/encounters",
        headers=admin,
        json={"patient_id": str(uuid4()), "reason": "Fever and cough"},
    )
    assert visit.status_code == 403, visit.text
    assert visit.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


@pytest.mark.asyncio
async def test_payment_notice_does_not_capture_funds(client, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/billing/payment-notices",
        headers=admin,
        json={"amount": 40, "method": "bank_transfer", "reference": "TT12345"},
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["funds_captured"] is False
    assert body["amount"] == 40
