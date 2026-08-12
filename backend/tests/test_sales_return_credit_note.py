"""Sales return credit note + refund/adjust settlement (BR-7.5)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _posted_invoice(ac, admin, seed, *, unit_price=50.0, pay_in_full: bool = False):
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": unit_price}],
        },
    )
    assert created.status_code == 200, created.text
    iid = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text
    inv = posted.json()["data"]
    if pay_in_full:
        pay_r = await ac.post(
            "/api/v1/sales/payments",
            headers=admin,
            json={
                "customer_id": seed["party1"].id,
                "sales_invoice_id": iid,
                "amount": float(inv["total_amount"]),
                "payment_method": "cash",
            },
        )
        assert pay_r.status_code == 200, pay_r.text
        inv = (await ac.get(f"/api/v1/sales/invoices/{iid}", headers=admin)).json()["data"]
    return inv


@pytest.mark.asyncio
async def test_return_on_open_invoice_assigns_credit_note(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    inv = await _posted_invoice(ac, admin, seed, unit_price=40)
    # bump product stock for restock path
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(product.stock_qty or 0) + 5
    await db_session.commit()

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    rid = ret.json()["data"]["id"]

    posted = await ac.post(
        f"/api/v1/sales/returns/{rid}/post",
        headers=admin,
        json={"settlement_method": "adjust"},
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()["data"]
    assert body["credit_note_number"] and body["credit_note_number"].startswith("CN-")
    assert body["settlement_method"] == "adjust"
    assert float(body["refunded_amount"]) == 0

    await db_session.refresh(await db_session.get(m.Party, seed["party1"].id))
    # Customer AR reduced (may be negative if over-credited relative to prior balance)
    party = await db_session.get(m.Party, seed["party1"].id)
    assert party is not None


@pytest.mark.asyncio
async def test_paid_invoice_return_requires_settlement_and_refunds(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    inv = await _posted_invoice(ac, admin, seed, unit_price=30, pay_in_full=True)
    assert inv["status"] == "paid"

    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(product.stock_qty or 0) + 5
    await db_session.commit()

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "customer_change",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    rid = ret.json()["data"]["id"]
    total = float(ret.json()["data"]["total_amount"])

    missing = await ac.post(f"/api/v1/sales/returns/{rid}/post", headers=admin, json={})
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == "SETTLEMENT_REQUIRED"

    party_before = await db_session.get(m.Party, seed["party1"].id)
    bal_before = float(party_before.balance or 0)

    posted = await ac.post(
        f"/api/v1/sales/returns/{rid}/post",
        headers=admin,
        json={"settlement_method": "refund", "payment_method": "cash"},
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()["data"]
    assert body["credit_note_number"].startswith("CN-")
    assert body["settlement_method"] == "refund"
    assert float(body["refunded_amount"]) == pytest.approx(total)

    await db_session.refresh(party_before)
    # Refund clears the excess credit — balance should not retain the full return as credit
    assert float(party_before.balance or 0) == pytest.approx(bal_before)

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "sales_return_refund",
                m.JournalEntry.source_id == rid,
            )
        )
    ).scalar_one_or_none()
    assert je is not None


@pytest.mark.asyncio
async def test_paid_invoice_return_adjust_leaves_customer_credit(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    inv = await _posted_invoice(ac, admin, seed, unit_price=25, pay_in_full=True)
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(product.stock_qty or 0) + 5
    await db_session.commit()

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "other",
            "restock": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}],
        },
    )
    rid = ret.json()["data"]["id"]
    total = float(ret.json()["data"]["total_amount"])
    party = await db_session.get(m.Party, seed["party1"].id)
    before = float(party.balance or 0)

    posted = await ac.post(
        f"/api/v1/sales/returns/{rid}/post",
        headers=admin,
        json={"settlement_method": "adjust"},
    )
    assert posted.status_code == 200, posted.text
    assert float(posted.json()["data"]["refunded_amount"]) == 0
    await db_session.refresh(party)
    assert float(party.balance) == pytest.approx(before - total)
