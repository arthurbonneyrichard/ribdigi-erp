"""Retail arithmetic fixture: stock 20, cost 60, exclusive price 100, tax 10%, sell 2.

Expected: total 220, revenue 200, tax 20, COGS 120, remaining stock 18.
The 10% rate is a test fixture, not tax guidance.
A repeated client_request_id must not sell or post again.
"""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import func, select

from app import models as m
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_sale_arithmetic_fixture_posts_once(client, db_session):
    ac, seed = client
    product = seed["p1"]
    product_id = product.id
    tenant_id = seed["t1"].id
    rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Fixture VAT 10",
        rate=10,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=False,
        is_active=True,
        is_reverse_charge=False,
    )
    db_session.add(rate)
    await db_session.flush()
    product.cost_price = 60
    product.selling_price = 100
    product.stock_qty = 20
    product.tax_rate_id = rate.id
    product.tax_supply_class = "standard"
    await db_session.commit()

    headers = await _cashier(ac)
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            admin = await _admin(ac, seed)
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=admin,
                json={"actual_cash": 0},
            )

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 0},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]

    body = {
        "session_id": session_id,
        "client_request_id": "retail-arith-220-001",
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 100}],
    }
    first = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    assert data.get("idempotent_replay") is not True
    assert float(data["total"]) == pytest.approx(220)
    assert float(data["tax"]) == pytest.approx(20)
    assert float(data["subtotal"]) == pytest.approx(200)
    sale_id = data["id"]

    second = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == sale_id
    assert second.json()["data"].get("idempotent_replay") is True

    db_session.expire_all()
    stock = (
        await db_session.execute(select(m.Product.stock_qty).where(m.Product.id == product_id))
    ).scalar_one()
    assert float(stock) == pytest.approx(18)

    journal_count = (
        await db_session.execute(
            select(func.count()).select_from(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "pos_sale",
                m.JournalEntry.source_id == sale_id,
            )
        )
    ).scalar_one()
    assert int(journal_count) == 1

    lines = (
        await db_session.execute(
            select(m.Account.code, m.JournalEntryLine.debit, m.JournalEntryLine.credit)
            .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
            .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
            .where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_id == sale_id,
            )
        )
    ).all()
    by_code: dict[str, tuple[float, float]] = {}
    for code, debit, credit in lines:
        prev = by_code.get(code, (0.0, 0.0))
        by_code[code] = (prev[0] + float(debit or 0), prev[1] + float(credit or 0))

    assert by_code["1000"][0] == pytest.approx(220)
    assert by_code["4000"][1] == pytest.approx(200)
    assert by_code["2100"][1] == pytest.approx(20)
    assert by_code["5000"][0] == pytest.approx(120)
    assert by_code["1200"][1] == pytest.approx(120)
    debit_total = sum(pair[0] for pair in by_code.values())
    credit_total = sum(pair[1] for pair in by_code.values())
    assert debit_total == pytest.approx(credit_total)
    assert debit_total == pytest.approx(340)
