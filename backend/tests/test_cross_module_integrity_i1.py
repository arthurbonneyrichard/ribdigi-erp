"""Stage 18 I1: cross-module integrity — inventory Σ · TB/GL · POS money-path."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import func, select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _sum_movements(
    db, *, tenant_id: str, product_id: str, warehouse_id: str | None = None
) -> float:
    stmt = select(func.coalesce(func.sum(m.StockMovement.quantity), 0)).where(
        m.StockMovement.tenant_id == tenant_id,
        m.StockMovement.product_id == product_id,
    )
    if warehouse_id is not None:
        stmt = stmt.where(m.StockMovement.warehouse_id == warehouse_id)
    return float((await db.execute(stmt)).scalar_one() or 0)


async def _wh_qty(db, tenant_id: str, warehouse_id: str, product_id: str) -> float:
    row = (
        await db.execute(
            select(m.WarehouseStock).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == warehouse_id,
                m.WarehouseStock.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    return float(row.quantity) if row else 0.0


async def _account_balance(db, tenant_id: str, code: str) -> float:
    row = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == code)
        )
    ).scalar_one()
    return float(row.balance or 0)


async def _pos_counts(db, tenant_id: str, session_id: str | None = None) -> dict:
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
            select(func.count()).select_from(m.PosPayment).where(m.PosPayment.tenant_id == tenant_id)
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
async def test_inventory_qty_equals_stage17_movement_chain(client, db_session):
    """Inventory qty = Σ movements after Stage 17 stock-in / adjust / warehouse ops."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S18 I1 Stock SKU",
        sku="S18-I1-STOCK",
        cost_price=2.5,
        selling_price=10,
        stock_qty=0,
    )
    wh = m.Warehouse(tenant_id=tenant_id, name="S18 I1 WH", code="S18I1WH")
    db_session.add_all([product, wh])
    await db_session.commit()
    product_id, warehouse_id = product.id, wh.id

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 50,
            "warehouse_id": warehouse_id,
            "notes": "s18-i1 receive",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    adjust = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=headers,
        json={
            "quantity": -3,
            "reason": "damage",
            "warehouse_id": warehouse_id,
            "notes": "s18-i1 damage",
        },
    )
    assert adjust.status_code == 200, adjust.text

    stock_out = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 7,
            "warehouse_id": warehouse_id,
            "notes": "s18-i1 ship",
        },
    )
    assert stock_out.status_code == 200, stock_out.text

    db_session.expire_all()
    product = await db_session.get(m.Product, product_id)
    expected = 50 - 3 - 7
    assert float(product.stock_qty) == pytest.approx(expected)
    assert await _sum_movements(db_session, tenant_id=tenant_id, product_id=product_id) == pytest.approx(
        expected
    )
    assert await _wh_qty(db_session, tenant_id, warehouse_id, product_id) == pytest.approx(expected)
    assert await _sum_movements(
        db_session, tenant_id=tenant_id, product_id=product_id, warehouse_id=warehouse_id
    ) == pytest.approx(expected)

    types = {
        row[0]
        for row in (
            await db_session.execute(
                select(m.StockMovement.movement_type).where(
                    m.StockMovement.tenant_id == tenant_id,
                    m.StockMovement.product_id == product_id,
                )
            )
        ).all()
    }
    assert {"stock_in", "adjustment", "stock_out"}.issubset(types)


@pytest.mark.asyncio
async def test_accounting_tb_inventory_gl_and_ar_sanity(client, db_session):
    """Journals/TB balanced; Inventory GL + AR move sanely after invoice post."""
    ac, seed = client
    headers = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = m.Product(
        tenant_id=tenant_id,
        name="S18 I1 GL SKU",
        sku="S18-I1-GL",
        cost_price=4,
        selling_price=25,
        stock_qty=0,
        tax_exempt=True,
    )
    db_session.add(product)
    await db_session.flush()

    # Seed stock via stock-in so invoice post is not blocked
    product_id = product.id
    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product_id, "quantity": 20, "notes": "s18-i1 gl stock"},
    )
    assert stock_in.status_code == 200, stock_in.text

    inv_before = await _account_balance(db_session, tenant_id, "1200")
    ar_before = await _account_balance(db_session, tenant_id, "1100")
    cogs_before = await _account_balance(db_session, tenant_id, "5000")

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "S18 I1 AR Customer", "credit_limit": 5000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 5,
                    "unit_price": 25,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    db_session.expire_all()
    product = await db_session.get(m.Product, product_id)
    assert float(product.stock_qty) == pytest.approx(15)
    assert await _sum_movements(
        db_session, tenant_id=tenant_id, product_id=product_id
    ) == pytest.approx(15)

    expected_ar = 125.0  # 5 × 25
    expected_cogs = 20.0  # 5 × 4

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    inv_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_invoice" and j.get("source_id") == invoice_id
    ]
    assert len(inv_jes) == 1
    assert float(inv_jes[0]["total_debit"]) == pytest.approx(float(inv_jes[0]["total_credit"]))
    assert float(inv_jes[0]["total_debit"]) == pytest.approx(expected_ar + expected_cogs)

    assert await _account_balance(db_session, tenant_id, "1200") == pytest.approx(
        inv_before - expected_cogs
    )
    assert await _account_balance(db_session, tenant_id, "1100") == pytest.approx(
        ar_before + expected_ar
    )
    assert await _account_balance(db_session, tenant_id, "5000") == pytest.approx(
        cogs_before + expected_cogs
    )

    tb = await ac.get("/api/v1/accounting/trial-balance", headers=super_h)
    assert tb.status_code == 200, tb.text
    tdata = tb.json()["data"]
    assert tdata["balanced"] is True
    assert float(tdata["total_debit"]) == pytest.approx(float(tdata["total_credit"]))
    by_code = {r["code"]: r for r in tdata["rows"]}
    assert "1100" in by_code and "1200" in by_code and "5000" in by_code

    aging = await ac.get("/api/v1/credit/aging?kind=receivable", headers=headers)
    assert aging.status_code == 200, aging.text
    assert float(aging.json()["data"]["total_due"]) >= expected_ar


@pytest.mark.asyncio
async def test_pos_money_path_no_orphans_and_stock_reconciles(client, db_session):
    """POS success links sale/payment/JE/stock; stock-fail leaves no orphans."""
    ac, seed = client
    cashier = await _cashier(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = m.Product(
        tenant_id=tenant_id,
        name="S18 I1 POS SKU",
        sku="S18-I1-POS",
        cost_price=3,
        selling_price=15,
        stock_qty=0,
        reserved_qty=0,
        tax_exempt=True,
    )
    db_session.add(product)
    await db_session.commit()
    product_id = product.id

    mgr = await _mgr(ac)
    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=mgr,
        json={"product_id": product_id, "quantity": 8, "notes": "s18-i1 pos stock"},
    )
    assert stock_in.status_code == 200, stock_in.text

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    before = await _pos_counts(db_session, tenant_id, session_id)

    denied = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 99}],
        },
    )
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"]["code"] == "INSUFFICIENT_STOCK"

    await db_session.commit()
    after_fail = await _pos_counts(db_session, tenant_id, session_id)
    assert after_fail == before
    db_session.expire_all()
    product = await db_session.get(m.Product, product_id)
    assert float(product.stock_qty) == pytest.approx(8)
    assert await _sum_movements(
        db_session, tenant_id=tenant_id, product_id=product_id
    ) == pytest.approx(8)

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    expected_total = 30.0

    await db_session.commit()
    db_session.expire_all()
    product = await db_session.get(m.Product, product_id)
    assert float(product.stock_qty) == pytest.approx(6)
    assert await _sum_movements(
        db_session, tenant_id=tenant_id, product_id=product_id
    ) == pytest.approx(6)

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
    assert float(jes[0].total_debit) == pytest.approx(float(jes[0].total_credit))
    # Cash/revenue 30 + COGS 6 (2 × 3)
    assert float(jes[0].total_debit) == pytest.approx(expected_total + 6)

    orphan_pays = (
        await db_session.execute(
            select(func.count())
            .select_from(m.PosPayment)
            .where(
                m.PosPayment.tenant_id == tenant_id,
                m.PosPayment.sale_id.is_(None),
            )
        )
    ).scalar_one()
    assert int(orphan_pays) == 0

    orphan_jes = (
        await db_session.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "pos_sale",
                m.JournalEntry.source_id.is_(None),
            )
        )
    ).scalar_one()
    assert int(orphan_jes) == 0

    success = await _pos_counts(db_session, tenant_id, session_id)
    assert success["tx"] == before["tx"] + 1
    assert success["pay"] == before["pay"] + 1
    assert success["je"] == before["je"] + 1
    assert success["sale_count"] == before["sale_count"] + 1
    assert success["cash_sales"] == pytest.approx(before["cash_sales"] + expected_total)

    tb = await accounting_svc.trial_balance(db_session, tenant_id)
    assert tb["balanced"] is True
