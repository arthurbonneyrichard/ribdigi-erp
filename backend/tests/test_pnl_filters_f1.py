"""P&L date / store / branch filters (BR-10.6 / BR-14.5)."""

from __future__ import annotations

from datetime import datetime, timedelta

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
async def test_pnl_date_and_store_filters(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.cost_price = 2
    product.selling_price = 10
    await db_session.commit()

    branch = m.Branch(tenant_id=tenant_id, code="BR-N", name="North Region")
    db_session.add(branch)
    await db_session.flush()
    store_a = m.Store(
        tenant_id=tenant_id, code="SA", name="Store A", branch_id=branch.id, is_active=True
    )
    store_b = m.Store(
        tenant_id=tenant_id, code="SB", name="Store B", branch_id=None, is_active=True
    )
    db_session.add_all([store_a, store_b])
    await db_session.flush()
    wh_a = m.Warehouse(
        tenant_id=tenant_id, store_id=store_a.id, name="WH A", code="WH-A"
    )
    wh_b = m.Warehouse(
        tenant_id=tenant_id, store_id=store_b.id, name="WH B", code="WH-B"
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.commit()

    for wh_id in (wh_a.id, wh_b.id):
        stock = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": product.id, "quantity": 50, "warehouse_id": wh_id},
        )
        assert stock.status_code == 200, stock.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "P&L Buyer", "credit_limit": 10000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    async def post_invoice(store_id: str, qty: int) -> str:
        inv = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={
                "customer_id": customer_id,
                "store_id": store_id,
                "items": [
                    {"product_id": product.id, "quantity": qty, "unit_price": 10}
                ],
            },
        )
        assert inv.status_code == 200, inv.text
        invoice_id = inv.json()["data"]["id"]
        posted = await ac.post(
            f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers
        )
        assert posted.status_code == 200, posted.text
        return invoice_id

    inv_a = await post_invoice(store_a.id, 3)  # revenue 30
    inv_b = await post_invoice(store_b.id, 5)  # revenue 50

    # Backdate store B invoice journal into the past
    past = datetime.utcnow() - timedelta(days=40)
    je_b = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "sales_invoice",
                m.JournalEntry.source_id == inv_b,
            )
        )
    ).scalar_one()
    je_b.entry_date = past
    await db_session.commit()

    lifetime = await ac.get("/api/v1/accounting/profit-loss", headers=headers)
    assert lifetime.status_code == 200, lifetime.text
    life = lifetime.json()["data"]
    assert life["mode"] == "balances"
    assert float(life["revenue"]) >= 80

    recent_from = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    period = await ac.get(
        f"/api/v1/accounting/profit-loss?from_date={recent_from}",
        headers=headers,
    )
    assert period.status_code == 200, period.text
    pdata = period.json()["data"]
    assert pdata["mode"] == "journals"
    # Only store A invoice (30) in the recent window; store B backdated out
    assert abs(float(pdata["revenue"]) - 30) < 0.01
    assert abs(float(pdata["cogs"]) - 6) < 0.01  # 3 × 2
    assert abs(float(pdata["gross_profit"]) - 24) < 0.01

    by_store = await ac.get(
        f"/api/v1/accounting/profit-loss?store_id={store_a.id}",
        headers=headers,
    )
    assert by_store.status_code == 200, by_store.text
    sdata = by_store.json()["data"]
    assert sdata["store_id"] == store_a.id
    assert abs(float(sdata["revenue"]) - 30) < 0.01

    by_branch = await ac.get(
        f"/api/v1/reports/profit-loss?branch_id={branch.id}",
        headers=headers,
    )
    assert by_branch.status_code == 200, by_branch.text
    bdata = by_branch.json()["data"]
    assert bdata["branch_id"] == branch.id
    assert abs(float(bdata["revenue"]) - 30) < 0.01

    store_b_pnl = await ac.get(
        f"/api/v1/accounting/profit-loss?store_id={store_b.id}",
        headers=headers,
    )
    assert store_b_pnl.status_code == 200
    assert abs(float(store_b_pnl.json()["data"]["revenue"]) - 50) < 0.01

    assert inv_a
