"""Till returns: refund items from a till receipt (BR-7.5 / BR-8)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _fresh_shift(ac, headers) -> str:
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(f"/api/v1/pos/sessions/{sid}/close", headers=headers, json={"actual_cash": 0})
    opened = await ac.post("/api/v1/pos/sessions/open", headers=headers, json={"opening_cash": 100})
    assert opened.status_code == 200, opened.text
    data = opened.json()["data"]
    return data.get("session_id") or data["id"]


@pytest.mark.asyncio
async def test_till_return_refunds_cash_restocks_and_limits_quantity(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 50
    await db_session.commit()
    session_id = await _fresh_shift(ac, headers)

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 3, "unit_price": 50}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    sale_total = float(sale.json()["data"]["total"])

    found = await ac.get("/api/v1/pos/receipts", headers=headers)
    assert found.status_code == 200, found.text
    assert any(r["id"] == sale_id for r in found.json()["data"])

    receipt = await ac.get(f"/api/v1/pos/sales/{sale_id}/returnable", headers=headers)
    assert receipt.status_code == 200, receipt.text
    line = receipt.json()["data"]["lines"][0]
    assert line["returnable_quantity"] == 3
    unit_refund = line["unit_refund"]
    assert abs(unit_refund * 3 - sale_total) < 0.05

    await db_session.refresh(product)
    stock_before = float(product.stock_qty)

    ret = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns",
        headers=headers,
        json={"items": [{"product_id": product.id, "quantity": 1}], "reason": "defective"},
    )
    assert ret.status_code == 200, ret.text
    data = ret.json()["data"]
    assert data["status"] == "posted"
    assert data["sales_invoice_id"] is None
    assert data["transaction_id"] == sale_id
    assert data["refund_payment_method"] == "cash"
    assert abs(float(data["refunded_amount"]) - unit_refund) < 0.01
    # The cash refund came out of the drawer, so the expected count drops.
    assert abs(float(data["session"]["cash_out"]) - unit_refund) < 0.01

    await db_session.refresh(product)
    assert abs(float(product.stock_qty) - (stock_before + 1)) < 1e-6

    # Only what is left on the receipt can still be returned.
    too_many = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns",
        headers=headers,
        json={"items": [{"product_id": product.id, "quantity": 3}], "reason": "other"},
    )
    assert too_many.status_code == 400, too_many.text

    # A damaged item is refunded but not put back on the shelf.
    damaged = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/returns",
        headers=headers,
        json={
            "items": [{"product_id": product.id, "quantity": 1, "restock": False}],
            "reason": "damaged",
            "refund_method": "mobile_money",
        },
    )
    assert damaged.status_code == 200, damaged.text
    await db_session.refresh(product)
    assert abs(float(product.stock_qty) - (stock_before + 1)) < 1e-6

    report = await ac.get(f"/api/v1/pos/sessions/{session_id}/report", headers=headers)
    assert report.status_code == 200, report.text
    assert report.json()["data"]["summary"]["return_count"] == 2

    journals = (
        await db_session.execute(
            select(m.JournalEntry).where(m.JournalEntry.source_type == "sales_return_refund")
        )
    ).scalars().all()
    assert len(journals) >= 2


@pytest.mark.asyncio
async def test_till_return_store_credit_needs_a_customer(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 5
    product.selling_price = 20
    await db_session.commit()
    session_id = await _fresh_shift(ac, headers)
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 20}],
        },
    )
    assert sale.status_code == 200, sale.text
    res = await ac.post(
        f"/api/v1/pos/sales/{sale.json()['data']['id']}/returns",
        headers=headers,
        json={
            "items": [{"product_id": product.id, "quantity": 1}],
            "reason": "customer_change",
            "refund_method": "store_credit",
        },
    )
    assert res.status_code == 400, res.text
