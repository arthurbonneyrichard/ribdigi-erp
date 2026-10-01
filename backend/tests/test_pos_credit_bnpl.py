"""POS buy-now-pay-later uses the existing AR invoice + customer payment ledger."""

from __future__ import annotations

from sqlalchemy import select

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _open_shift(ac, headers, admin_headers):
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=admin_headers,
                json={"actual_cash": 0},
            )
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 0},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()["data"].get("session_id") or opened.json()["data"]["id"]


@pytest.mark.asyncio
async def test_pos_credit_requires_customer(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 10
    await db_session.commit()
    session_id = await _open_shift(ac, headers, admin)

    r = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "credit",
            "status": "completed",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail") or ""
    assert "customer" in str(detail).lower()


@pytest.mark.asyncio
async def test_pos_credit_opens_ar_and_accepts_repayment(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    customer = seed["party1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    customer.credit_limit = 200
    customer.balance = 0
    await db_session.commit()
    session_id = await _open_shift(ac, headers, admin)

    r = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "credit",
            "status": "completed",
            "party_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["payment_status"] == "unpaid"
    assert float(data["paid_amount"]) == 0
    assert float(data["balance_due"]) > 0
    assert data["sales_invoice_id"]
    invoice_id = data["sales_invoice_id"]
    sale_total = float(data["total"])

    aging = await ac.get("/api/v1/credit/aging?kind=receivable", headers=admin)
    assert aging.status_code == 200, aging.text
    docs = aging.json()["data"].get("documents") or []
    assert any(d.get("id") == invoice_id for d in docs)

    credit = await ac.get(f"/api/v1/customers/{customer.id}/credit", headers=admin)
    assert credit.status_code == 200, credit.text
    info = credit.json()["data"]
    assert abs(float(info["outstanding_balance"]) - sale_total) < 0.01
    assert info["open_invoice_count"] == 1

    receipt = await ac.get(f"/api/v1/pos/sales/{data['id']}/receipt", headers=headers)
    assert receipt.status_code == 200, receipt.text
    text = receipt.json()["data"].get("text") or ""
    assert "Balance due" in text
    assert "UNPAID" in text.upper()

    pay = await ac.post(
        f"/api/v1/customers/{customer.id}/payments",
        headers=admin,
        json={
            "customer_id": customer.id,
            "amount": round(sale_total / 2, 2),
            "payment_method": "cash",
            "notes": "Received 2026-09-30",
        },
    )
    assert pay.status_code == 200, pay.text

    hist = await ac.get(f"/api/v1/customers/{customer.id}/history", headers=admin)
    assert hist.status_code == 200, hist.text
    payments = hist.json()["data"].get("payments") or []
    assert len(payments) >= 1
    assert payments[0]["payment_method"] == "cash"

    inv = (
        await db_session.execute(select(m.SalesInvoice).where(m.SalesInvoice.id == invoice_id))
    ).scalar_one()
    await db_session.refresh(inv)
    assert inv.status in {"partial", "overdue"}
    assert float(inv.paid_amount) > 0
    assert float(inv.total_amount) - float(inv.paid_amount) > 0.01


@pytest.mark.asyncio
async def test_pos_partial_cash_and_credit(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    customer = seed["party1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    customer.credit_limit = 500
    await db_session.commit()
    session_id = await _open_shift(ac, headers, admin)

    body = {
        "session_id": session_id,
        "status": "completed",
        "party_id": customer.id,
        "payment_method": "split",
        "items": [{"product_id": product.id, "quantity": 1}],
        "payments": [
            {"payment_method": "cash", "amount": 4},
            {"payment_method": "credit", "amount": 6},
        ],
    }
    r = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    if r.status_code == 400:
        detail = r.json().get("detail") or {}
        if isinstance(detail, dict) and detail.get("code") == "PAYMENT_TOTAL_MISMATCH":
            due = float(detail["sale_total"])
            cash = round(due * 0.4, 2)
            credit_amt = round(due - cash, 2)
            body["payments"] = [
                {"payment_method": "cash", "amount": cash},
                {"payment_method": "credit", "amount": credit_amt},
            ]
            r = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["payment_status"] == "partially_paid"
    assert float(data["paid_amount"]) > 0
    assert float(data["balance_due"]) > 0
    assert data["sales_invoice_id"]


@pytest.mark.asyncio
async def test_pos_credit_enforces_existing_limit(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    admin = await _admin(ac, seed)
    product = seed["p1"]
    customer = seed["party1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 50
    customer.credit_limit = 5
    customer.balance = 0
    await db_session.commit()
    session_id = await _open_shift(ac, headers, admin)

    r = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "credit",
            "status": "completed",
            "party_id": customer.id,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert r.status_code == 409, r.text
    detail = r.json().get("detail") or {}
    assert detail.get("code") == "CREDIT_LIMIT_EXCEEDED"
