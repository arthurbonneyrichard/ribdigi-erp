"""Stage 15 R1: sales return chain — warehouse restock, FX AR, store JE, tax/COGS reverse."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app.inventory import apply_stock_change, get_or_create_warehouse_stock
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _codes_by_account(db_session, tenant_id: str, lines: list[dict]) -> dict[str, list[dict]]:
    account_ids = {ln["account_id"] for ln in lines}
    accounts = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == tenant_id,
                m.Account.id.in_(account_ids),
            )
        )
    ).scalars().all()
    code_by_id = {a.id: a.code for a in accounts}
    by_code: dict[str, list[dict]] = {}
    for ln in lines:
        by_code.setdefault(code_by_id[ln["account_id"]], []).append(ln)
    return by_code


@pytest.mark.asyncio
async def test_return_restock_warehouse_tax_cogs_store_journal(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    store = await create_store(
        db_session, tenant_id=tenant_id, code="R1WH", name="R1 Return Store"
    )
    store_id = store.id
    wh = await warehouse_for_store(db_session, tenant_id, store_id)
    warehouse_id = wh.id
    product_id = seed["p1"].id

    product = seed["p1"]
    product.cost_price = 4
    product.stock_qty = 0
    product.reserved_qty = 0
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=20,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=warehouse_id,
    )
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "R1 Chain Customer", "credit_limit": 10000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    # 2 @ 50, tax 10% → net 100, tax 10, total 110; COGS 8
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "store_id": store_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                    "unit_price": 50,
                    "tax_rate": 10,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    await db_session.commit()
    db_session.expire_all()
    wh_stock = await get_or_create_warehouse_stock(
        db_session, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    assert float(wh_stock.quantity) == pytest.approx(18)
    cust_after_sale = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    balance_after_sale = float(cust_after_sale.json()["data"]["balance"])
    assert balance_after_sale == pytest.approx(110)

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    return_id = ret.json()["data"]["id"]
    # Return 1 @ 50 + 10% tax → 55
    assert float(ret.json()["data"]["total_amount"]) == pytest.approx(55)

    posted_ret = await ac.post(f"/api/v1/sales/returns/{return_id}/post", headers=headers)
    assert posted_ret.status_code == 200, posted_ret.text
    pdata = posted_ret.json()["data"]
    assert pdata["status"] == "posted"
    assert pdata["credit_note_number"]
    assert pdata["credit_note_number"].startswith("CN-") or "CN" in pdata["credit_note_number"]

    await db_session.commit()
    db_session.expire_all()

    # Warehouse + consolidated stock restored for 1 unit
    wh_stock = await get_or_create_warehouse_stock(
        db_session, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    assert float(wh_stock.quantity) == pytest.approx(19)
    product_row = (
        await db_session.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()
    assert float(product_row.stock_qty) == pytest.approx(19)

    movements = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_type == "sales_return",
                m.StockMovement.reference_id == return_id,
            )
        )
    ).scalars().all()
    assert movements
    assert all(mv.warehouse_id == warehouse_id for mv in movements)
    assert sum(float(mv.quantity) for mv in movements) == pytest.approx(1)

    cust2 = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert float(cust2.json()["data"]["balance"]) == pytest.approx(balance_after_sale - 55)

    inv_after = await ac.get(f"/api/v1/sales/invoices/{invoice_id}", headers=headers)
    assert float(inv_after.json()["data"]["paid_amount"]) == pytest.approx(55)
    assert inv_after.json()["data"]["status"] == "partial"

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    ret_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_return" and j.get("source_id") == return_id
    ]
    assert len(ret_jes) == 1
    assert ret_jes[0].get("store_id") == store_id

    detail = await ac.get(
        f"/api/v1/accounting/journal-entries/{ret_jes[0]['id']}", headers=headers
    )
    by_code = await _codes_by_account(db_session, tenant_id, detail.json()["data"]["lines"])
    assert sum(float(ln["debit"]) for ln in by_code["4000"]) == pytest.approx(50)
    assert sum(float(ln["credit"]) for ln in by_code["1100"]) == pytest.approx(55)
    assert sum(float(ln["debit"]) for ln in by_code["2100"]) == pytest.approx(5)
    assert sum(float(ln["debit"]) for ln in by_code["1200"]) == pytest.approx(4)
    assert sum(float(ln["credit"]) for ln in by_code["5000"]) == pytest.approx(4)


@pytest.mark.asyncio
async def test_return_fx_safe_customer_balance_and_journal(client, db_session):
    """Return AR/balance use invoice exchange_rate → base (Stage 15 R1)."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.cost_price = 0  # isolate FX math from COGS
    product.stock_qty = 30
    product.reserved_qty = 0
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "R1 FX Customer", "credit_limit": 50000},
    )
    customer_id = cust.json()["data"]["id"]

    # Doc currency USD @ rate 2 → base; 1 × 40 = 40 USD → 80 base
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "currency": "USD",
            "exchange_rate": 2,
            "items": [
                {"product_id": product.id, "quantity": 1, "unit_price": 40, "tax_rate": 0}
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    assert float(created.json()["data"]["exchange_rate"]) == pytest.approx(2)
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    cust_sale = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert float(cust_sale.json()["data"]["balance"]) == pytest.approx(80)

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    return_id = ret.json()["data"]["id"]
    assert float(ret.json()["data"]["total_amount"]) == pytest.approx(40)

    posted_ret = await ac.post(f"/api/v1/sales/returns/{return_id}/post", headers=headers)
    assert posted_ret.status_code == 200, posted_ret.text

    cust2 = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert float(cust2.json()["data"]["balance"]) == pytest.approx(0)

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    ret_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_return" and j.get("source_id") == return_id
    ]
    assert len(ret_jes) == 1
    # Base amounts: 40 USD × 2 = 80
    assert float(ret_jes[0]["total_debit"]) == pytest.approx(80)
    assert float(ret_jes[0]["total_credit"]) == pytest.approx(80)
