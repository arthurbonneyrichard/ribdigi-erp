"""Standard-cost COGS on sales/POS/returns + P&L gross profit (BR-10.6)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_invoice_post_posts_cogs_and_pnl_gross_profit(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    product = seed["p1"]
    product.cost_price = 4
    product.selling_price = 10
    await db_session.commit()

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 20},
    )
    assert stock.status_code == 200, stock.text

    # Seed COA + capture inventory after stock-in (no GL on stock-in)
    accounts0 = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts0.status_code == 200
    inv0 = next(a for a in accounts0.json()["data"] if a["code"] == "1200")
    cogs0 = next(a for a in accounts0.json()["data"] if a["code"] == "5000")
    inv_bal0 = float(inv0["balance"])
    cogs_bal0 = float(cogs0["balance"])

    # Give inventory GL a starting balance so relief is visible (opening-style)
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Seed inventory for COGS test",
        lines=[
            {"account_code": "1200", "debit": 80, "credit": 0},
            {"account_code": "3000", "debit": 0, "credit": 80},
        ],
        source_type="manual",
    )
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "COGS Buyer", "credit_limit": 10000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product.id, "quantity": 3, "unit_price": 10}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    accounts1 = await ac.get("/api/v1/accounting/accounts", headers=headers)
    inv1 = next(a for a in accounts1.json()["data"] if a["code"] == "1200")
    cogs1 = next(a for a in accounts1.json()["data"] if a["code"] == "5000")
    # Seeded 80, then COGS relief 3×4=12 → 68
    assert abs(float(inv1["balance"]) - 68) < 0.01
    assert abs(float(cogs1["balance"]) - (cogs_bal0 + 12)) < 0.01

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "sales_invoice",
                m.JournalEntry.source_id == invoice_id,
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == je.id)
        )
    ).scalars().all()
    codes = []
    for ln in lines:
        acct = (
            await db_session.execute(select(m.Account).where(m.Account.id == ln.account_id))
        ).scalar_one()
        codes.append((acct.code, float(ln.debit), float(ln.credit)))
    assert any(c == "5000" and d == 12 for c, d, _ in codes)
    assert any(c == "1200" and cr == 12 for c, _, cr in codes)

    pnl = await ac.get("/api/v1/accounting/profit-loss", headers=headers)
    assert pnl.status_code == 200
    data = pnl.json()["data"]
    assert "gross_profit" in data
    assert "cogs" in data
    assert abs(float(data["cogs"]) - (cogs_bal0 + 12)) < 0.01
    assert abs(float(data["gross_profit"]) - (float(data["revenue"]) - float(data["cogs"]))) < 0.01
    assert abs(float(data["net_profit"]) - (float(data["revenue"]) - float(data["expense"]))) < 0.01

    # unused seed vars silence
    assert inv_bal0 >= 0


@pytest.mark.asyncio
async def test_sales_return_restock_reverses_cogs(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    product.cost_price = 5
    await db_session.commit()

    await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 10},
    )
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        description="Seed inv",
        lines=[
            {"account_code": "1200", "debit": 50, "credit": 0},
            {"account_code": "3000", "debit": 0, "credit": 50},
        ],
    )
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Return COGS Buyer", "credit_limit": 5000},
    )
    customer_id = cust.json()["data"]["id"]
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product.id, "quantity": 2, "unit_price": 20}],
        },
    )
    invoice_id = inv.json()["data"]["id"]
    assert (
        await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    ).status_code == 200

    accounts_mid = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cogs_mid = float(
        next(a for a in accounts_mid.json()["data"] if a["code"] == "5000")["balance"]
    )
    inv_mid = float(
        next(a for a in accounts_mid.json()["data"] if a["code"] == "1200")["balance"]
    )

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "restock": True,
            "reason": "other",
            "items": [{"product_id": product.id, "quantity": 1, "condition": "sellable"}],
        },
    )
    assert ret.status_code == 200, ret.text
    return_id = ret.json()["data"]["id"]
    posted = await ac.post(
        f"/api/v1/sales/returns/{return_id}/post",
        headers=headers,
        json={"settlement_method": "adjust"},
    )
    assert posted.status_code == 200, posted.text

    accounts_end = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cogs_end = float(
        next(a for a in accounts_end.json()["data"] if a["code"] == "5000")["balance"]
    )
    inv_end = float(
        next(a for a in accounts_end.json()["data"] if a["code"] == "1200")["balance"]
    )
    # Sale COGS 10, return reverses 5 → net COGS 5; inventory +5 vs mid
    assert abs(cogs_end - (cogs_mid - 5)) < 0.01
    assert abs(inv_end - (inv_mid + 5)) < 0.01
