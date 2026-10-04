"""POS shift report summary with discounts and returns (BR-8.2)."""

from __future__ import annotations

from datetime import datetime

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


@pytest.mark.asyncio
async def test_shift_report_includes_summary_discounts_and_returns(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 50
    await db_session.commit()

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=headers,
                json={"actual_cash": 0},
            )

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    session = opened.json()["data"]
    session_id = session.get("session_id") or session["id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "discount_amount": 5,
            "items": [{"product_id": product.id, "quantity": 2, "unit_price": 50}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_total = float(sale.json()["data"]["total"])

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SHIFT-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=20,
        total_amount=20,
        posted_at=datetime.utcnow(),
    )
    db_session.add(inv)
    await db_session.flush()
    me = (
        await db_session.execute(
            select(m.User).where(
                m.User.email == "super@alpha.example.com",
                m.User.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    ret = m.SalesReturn(
        tenant_id=tenant_id,
        return_number="SR-SHIFT-1",
        customer_id=seed["party1"].id,
        sales_invoice_id=inv.id,
        status="posted",
        reason="damaged",
        total_amount=10,
        created_by=me.id,
        posted_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db_session.add(ret)
    await db_session.commit()

    report = await ac.get(f"/api/v1/pos/sessions/{session_id}/report", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    assert "summary" in data
    assert data["summary"]["sale_count"] == 1
    assert abs(float(data["summary"]["discounts"]) - 5) < 0.01
    assert abs(float(data["summary"]["net_sales"]) - sale_total) < 0.01
    assert data["summary"]["return_count"] == 1
    assert abs(float(data["summary"]["return_total"]) - 10) < 0.01
    assert abs(float(data["summary"]["net_after_returns"]) - (sale_total - 10)) < 0.01
    assert data["returns"][0]["return_number"] == "SR-SHIFT-1"
    assert data["payment_breakdown"]["cash"] > 0

    other = m.SalesReturn(
        tenant_id=tenant_id,
        return_number="SR-SHIFT-OTHER",
        customer_id=seed["party1"].id,
        sales_invoice_id=inv.id,
        status="posted",
        reason="other",
        total_amount=99,
        created_by="00000000-0000-0000-0000-000000000099",
        created_at=datetime.utcnow(),
    )
    db_session.add(other)
    await db_session.commit()
    report2 = await ac.get(f"/api/v1/pos/sessions/{session_id}/report", headers=headers)
    assert report2.json()["data"]["summary"]["return_count"] == 1
