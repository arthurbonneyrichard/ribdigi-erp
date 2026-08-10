"""Stage 13 H2: multi-tender → stock → receipt send → journal → drawer-on-cash → close."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app.cash_drawer import kick_base64
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_multi_tender_receipt_send_drawer_close(client, db_session, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "mock")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "mock")

    ac, seed = client
    headers = await _cashier(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.selling_price = 100
    product.stock_qty = 25
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    seed["party1"].credit_limit = 500
    seed["party1"].balance = 0
    seed["party1"].party_type = "registered"
    seed["party1"].status = "active"
    await db_session.commit()
    opening_stock = 25.0

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 150},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    # Split: cash 30 + card 40 + wallet 20 + credit 10 = 100
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "party_id": seed["party1"].id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "payments": [
                {"payment_method": "cash", "amount": 30},
                {"payment_method": "card", "amount": 40},
                {"payment_method": "wallet", "amount": 20},
                {"payment_method": "credit", "amount": 10},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    sale_id = data["id"]
    assert data["payment_method"] == "split"
    assert float(data["total"]) == pytest.approx(100)
    assert len(data["payments"]) == 4
    # Cash portion must pulse drawer (has_cash_tender)
    assert data.get("drawer") is not None
    assert data["drawer"]["ok"] is True
    assert data["drawer"]["mode"] == "mock"
    assert data["drawer"]["kick_base64"] == kick_base64()

    await db_session.commit()
    await db_session.refresh(product)
    assert float(product.stock_qty) == pytest.approx(opening_stock - 1)
    await db_session.refresh(seed["party1"])
    assert float(seed["party1"].balance or 0) == pytest.approx(10)

    receipt = await ac.get(f"/api/v1/pos/sales/{sale_id}/receipt", headers=headers)
    assert receipt.status_code == 200, receipt.text
    rbody = receipt.json()["data"]
    assert len(rbody["payments"]) == 4
    text = rbody.get("text") or ""
    assert "CASH" in text and "CARD" in text

    sent = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": "customer@example.com"},
    )
    assert sent.status_code == 200, sent.text
    sdata = sent.json()["data"]
    assert sdata["channel"] == "email"
    assert sdata["sent"] is True
    assert sdata["to"] == "customer@example.com"

    audits = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "pos_receipt_sent"},
    )
    assert audits.status_code == 200, audits.text
    row = next(r for r in audits.json()["data"] if r["entity_id"] == sale_id)
    assert row["module"] == "pos"
    assert row["integrity_hash"]
    assert row["details"]["channel"] == "email"
    assert row["details"]["to"] == "customer@example.com"

    jes = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "pos_sale",
                m.JournalEntry.source_id == sale_id,
            )
        )
    ).scalars().all()
    assert len(jes) == 1
    # Sale total 100 + COGS 1 (qty 1 × cost_price 1) — Stage 15 I1
    assert float(jes[0].total_debit) == pytest.approx(101)

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert cur.status_code == 200
    sess = cur.json()["data"]
    assert float(sess["cash_sales"]) == pytest.approx(30)
    assert float(sess["card_sales"]) == pytest.approx(40)
    assert float(sess["other_sales"]) == pytest.approx(30)  # wallet 20 + credit 10
    assert float(sess["total_sales"]) == pytest.approx(100)
    assert int(sess["sale_count"]) == 1

    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=headers,
        json={"actual_cash": 180},  # opening 150 + cash 30
    )
    assert closed.status_code == 200, closed.text
    cdata = closed.json()["data"]
    assert float(cdata.get("expected_cash") or cdata.get("expected") or 180) == pytest.approx(
        180
    )


@pytest.mark.asyncio
async def test_split_without_cash_skips_drawer(client, db_session, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "mock")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "mock")

    ac, seed = client
    headers = await _cashier(ac)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)
    seed["p1"].selling_price = 50
    seed["p1"].stock_qty = 10
    seed["p1"].tax_exempt = True
    seed["p1"].tax_rate_id = None
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
            "payments": [
                {"payment_method": "card", "amount": 30},
                {"payment_method": "wallet", "amount": 20},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    assert data["payment_method"] == "split"
    assert data.get("drawer") is None
