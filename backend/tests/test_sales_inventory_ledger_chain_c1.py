"""Stage 15 C1: Sales invoice → stock movement → AR → tax report → JE account lines."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_invoice_stock_ar_tax_journal_chain(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product_id = seed["p1"].id
    tenant_id = seed["t1"].id

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=25,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()
    db_session.expire_all()

    product = (
        await db_session.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()
    opening_stock = float(product.stock_qty)

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "S15 C1 Ledger Customer",
            "email": "s15-c1@example.com",
            "party_type": "registered",
            "credit_limit": 2000,
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]
    balance0 = float(customer.json()["data"].get("balance") or 0)

    # 10 @ 5, discount 10, tax 15% → net 40, tax 6, total 46
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 10,
                    "unit_price": 5,
                    "tax_rate": 15,
                    "discount": 10,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv_body = created.json()["data"]
    invoice_id = inv_body["id"]
    assert float(inv_body["tax_amount"]) == pytest.approx(6)
    assert float(inv_body["total_amount"]) == pytest.approx(46)

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] in {"posted", "sent", "unpaid"}

    # Inventory: product qty + stock_movements reference
    db_session.expire_all()
    product = (
        await db_session.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()
    assert float(product.stock_qty) == pytest.approx(opening_stock - 10)

    movements = (
        await db_session.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_type == "sales_invoice",
                m.StockMovement.reference_id == invoice_id,
            )
        )
    ).scalars().all()
    assert movements, "expected stock_movements for posted sales invoice"
    assert sum(float(mv.quantity) for mv in movements) == pytest.approx(-10)
    assert any(mv.movement_type == "stock_out" for mv in movements)

    # Customer balance (base currency)
    cust = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert cust.status_code == 200
    assert float(cust.json()["data"]["balance"]) == pytest.approx(balance0 + 46)

    # Tax report includes this invoice's output tax
    now = datetime.utcnow()
    tax_resp = await ac.get(
        "/api/v1/reports/tax",
        headers=headers,
        params={
            "from_date": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "to_date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
        },
    )
    assert tax_resp.status_code == 200, tax_resp.text
    tax_data = tax_resp.json()["data"]
    assert int(tax_data.get("invoice_count") or 0) >= 1
    assert float(tax_data.get("output_tax") or 0) >= 6
    assert float(tax_data.get("output_tax_invoices") or 0) >= 6

    # Journal: source_type + account codes 1100 / 4000 / 2100
    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert journals.status_code == 200
    inv_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_invoice" and j.get("source_id") == invoice_id
    ]
    assert len(inv_jes) == 1
    assert float(inv_jes[0]["total_debit"]) == pytest.approx(46)

    detail = await ac.get(
        f"/api/v1/accounting/journal-entries/{inv_jes[0]['id']}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    lines = detail.json()["data"]["lines"]
    assert len(lines) >= 3

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
        code = code_by_id.get(ln["account_id"])
        assert code, f"missing account for line {ln}"
        by_code.setdefault(code, []).append(ln)

    assert "1100" in by_code
    assert "4000" in by_code
    assert "2100" in by_code
    assert sum(float(ln["debit"]) for ln in by_code["1100"]) == pytest.approx(46)
    assert sum(float(ln["credit"]) for ln in by_code["4000"]) == pytest.approx(40)
    assert sum(float(ln["credit"]) for ln in by_code["2100"]) == pytest.approx(6)
