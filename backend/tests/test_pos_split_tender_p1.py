"""Stage 3 P1: POS split tender via pos_payments (BR-8.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import pos as pos_svc
from tests.conftest import auth_headers


async def _open_shift(ac, headers, opening_cash: float = 200) -> str:
    r = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": opening_cash},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["session_id"]


@pytest.mark.asyncio
async def test_split_tender_records_payments_and_session_buckets(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    sid = await _open_shift(ac, headers)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    seed["p1"].selling_price = 100
    seed["p1"].tax_rate_id = None
    await db_session.commit()

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": sid,
            "status": "completed",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
            "payments": [
                {"payment_method": "cash", "amount": 40},
                {"payment_method": "card", "amount": 60},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    assert data["payment_method"] == "split"
    assert len(data["payments"]) == 2
    assert {p["payment_method"] for p in data["payments"]} == {"cash", "card"}
    assert abs(sum(float(p["amount"]) for p in data["payments"]) - float(data["total"])) < 0.02

    rows = (
        await db_session.execute(
            select(m.PosPayment).where(
                m.PosPayment.tenant_id == tenant_id,
                m.PosPayment.sale_id == data["id"],
            )
        )
    ).scalars().all()
    assert len(rows) == 2

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "pos_sale",
                m.JournalEntry.source_id == data["id"],
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == je.id)
        )
    ).scalars().all()
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")
    by_acct = {ln.account_id: float(ln.debit or 0) for ln in lines if float(ln.debit or 0) > 0}
    assert by_acct.get(cash.id) == 40
    assert by_acct.get(bank.id) == 60

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert cur.status_code == 200
    sess = cur.json()["data"]
    assert float(sess["cash_sales"]) == 40
    assert float(sess["card_sales"]) == 60

    receipt = await ac.get(f"/api/v1/pos/sales/{data['id']}/receipt", headers=headers)
    assert receipt.status_code == 200
    assert len(receipt.json()["data"]["payments"]) == 2
    assert "CASH" in receipt.json()["data"]["text"]
    assert "CARD" in receipt.json()["data"]["text"]


@pytest.mark.asyncio
async def test_split_tender_mismatch_and_credit_portion(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    sid = await _open_shift(ac, headers)
    seed["p1"].selling_price = 50
    seed["p1"].tax_rate_id = None
    seed["party1"].credit_limit = 1000
    seed["party1"].balance = 0
    seed["party1"].party_type = "registered"
    await db_session.commit()

    bad = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
            "payments": [
                {"payment_method": "cash", "amount": 10},
                {"payment_method": "card", "amount": 10},
            ],
        },
    )
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "PAYMENT_TOTAL_MISMATCH"

    ok = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": sid,
            "party_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
            "payments": [
                {"payment_method": "cash", "amount": 20},
                {"payment_method": "credit", "amount": 30},
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["payment_method"] == "split"
    await db_session.refresh(seed["party1"])
    assert float(seed["party1"].balance or 0) == 30


@pytest.mark.asyncio
async def test_single_tender_still_writes_pos_payment(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    sid = await _open_shift(ac, headers)
    seed["p1"].selling_price = 25
    seed["p1"].tax_rate_id = None
    await db_session.commit()

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": sid,
            "payment_method": "wallet",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    assert data["payment_method"] == "wallet"
    assert len(data["payments"]) == 1
    assert data["payments"][0]["payment_method"] == "wallet"


def test_resolve_sale_payments_helpers():
    single = pos_svc.resolve_sale_payments(total=12.5, payment_method="cash", payments=None)
    assert single == [
        {
            "payment_method": "cash",
            "amount": 12.5,
            "reference": None,
            "liquid_account_id": None,
        }
    ]
    split = pos_svc.resolve_sale_payments(
        total=100,
        payment_method="cash",
        payments=[
            {"payment_method": "cash", "amount": 35},
            {"payment_method": "card", "amount": 65},
        ],
    )
    assert pos_svc.primary_payment_method(split) == "split"
    assert pos_svc.credit_portion(split) == 0
    assert pos_svc.has_cash_tender(split) is True
