"""Stage 13 H1: POS sale atomicity — stock-fail leaves no orphans; success commits chain."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import func, select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _counts(db, tenant_id: str, session_id: str | None = None):
    tx_n = (
        await db.execute(
            select(func.count())
            .select_from(m.Transaction)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalar_one()
    pay_n = (
        await db.execute(
            select(func.count())
            .select_from(m.PosPayment)
            .where(m.PosPayment.tenant_id == tenant_id)
        )
    ).scalar_one()
    je_n = (
        await db.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "pos_sale",
            )
        )
    ).scalar_one()
    sale_count = 0
    cash_sales = 0.0
    if session_id:
        sess = await db.get(m.PosSession, session_id)
        assert sess is not None
        sale_count = int(sess.sale_count or 0)
        cash_sales = float(sess.cash_sales or 0)
    return {
        "tx": int(tx_n),
        "pay": int(pay_n),
        "je": int(je_n),
        "sale_count": sale_count,
        "cash_sales": cash_sales,
    }


@pytest.mark.asyncio
async def test_pos_sale_insufficient_stock_no_orphans(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.selling_price = 25
    product.stock_qty = 1
    product.reserved_qty = 0
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    before = await _counts(db_session, tenant_id, session_id)

    denied = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 5}],
        },
    )
    assert denied.status_code == 409, denied.text
    detail = denied.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_STOCK"
    assert float(detail["available"]) == pytest.approx(1)
    assert float(detail["requested"]) == pytest.approx(5)

    await db_session.commit()  # refresh visibility after request session closed
    after = await _counts(db_session, tenant_id, session_id)
    assert after["tx"] == before["tx"]
    assert after["pay"] == before["pay"]
    assert after["je"] == before["je"]
    assert after["sale_count"] == before["sale_count"]
    assert after["cash_sales"] == pytest.approx(before["cash_sales"])

    await db_session.refresh(product)
    assert float(product.stock_qty) == pytest.approx(1)


@pytest.mark.asyncio
async def test_pos_sale_aggregated_lines_reject_before_tx(client, db_session):
    """Two lines of 1 each against stock 1 must fail aggregated preflight (not pass line-by-line)."""
    ac, seed = client
    headers = await _cashier(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.selling_price = 10
    product.stock_qty = 1
    product.reserved_qty = 0
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    before_tx = (
        await db_session.execute(
            select(func.count())
            .select_from(m.Transaction)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalar_one()

    denied = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [
                {"product_id": product.id, "quantity": 1},
                {"product_id": product.id, "quantity": 1},
            ],
        },
    )
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"]["code"] == "INSUFFICIENT_STOCK"
    assert float(denied.json()["detail"]["requested"]) == pytest.approx(2)

    await db_session.commit()
    after_tx = (
        await db_session.execute(
            select(func.count())
            .select_from(m.Transaction)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalar_one()
    assert int(after_tx) == int(before_tx)


@pytest.mark.asyncio
async def test_pos_sale_success_commits_stock_journal_audit(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.selling_price = 40
    product.stock_qty = 10
    product.reserved_qty = 0
    product.tax_exempt = True
    await db_session.commit()
    opening = 10.0
    expected_total = 80.0

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 80},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 2}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    assert float(sale.json()["data"]["total"]) == pytest.approx(expected_total)

    await db_session.commit()
    await db_session.refresh(product)
    assert float(product.stock_qty) == pytest.approx(opening - 2)

    pays = (
        await db_session.execute(
            select(m.PosPayment).where(
                m.PosPayment.tenant_id == tenant_id,
                m.PosPayment.sale_id == sale_id,
            )
        )
    ).scalars().all()
    assert len(pays) == 1
    assert float(pays[0].amount) == pytest.approx(expected_total)

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
    # Sale total + COGS (qty 2 × cost_price 1) — Stage 15 I1
    assert float(jes[0].total_debit) == pytest.approx(expected_total + 2)

    audits = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "pos_sale_completed"},
    )
    assert audits.status_code == 200, audits.text
    row = next(r for r in audits.json()["data"] if r["entity_id"] == sale_id)
    assert row["module"] == "pos"
    assert row["integrity_hash"]

    sess = await db_session.get(m.PosSession, session_id)
    assert int(sess.sale_count or 0) == 1
    assert float(sess.cash_sales or 0) == pytest.approx(expected_total)
