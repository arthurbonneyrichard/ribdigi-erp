"""Stage 12 C1: Customer → quotation → order → invoice → payment chain + tax-on-net math."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.sales import calc_sale_line_amounts
from app.tax import TaxSpec
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_sale_line_tax_on_net_after_discount():
    # 10 × 5 = 50, discount 10 → net 40, tax 15% → 6, total 46
    spec = TaxSpec(
        rate_pct=15,
        pricing_mode="exclusive",
        is_reverse_charge=False,
        components=None,
        tax_rate_id=None,
        supply_category="standard",
    )
    sub, tax, total, disc = calc_sale_line_amounts(spec, 10, 5, 10)
    assert disc == 10
    assert sub == 40
    assert tax == 6
    assert total == 46


@pytest.mark.asyncio
async def test_customer_quote_order_invoice_payment_chain(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product_id = seed["p1"].id
    tenant_id = seed["t1"].id

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=20,
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
            "name": "OTC Chain Customer",
            "email": "otc-chain@example.com",
            "party_type": "registered",
            "credit_limit": 1000,
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]
    balance0 = float(customer.json()["data"].get("balance") or 0)

    # 10 @ 5, discount 10, tax 15% → expected invoice total 46
    quote = await ac.post(
        "/api/v1/sales/quotations",
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
    assert quote.status_code == 200, quote.text
    quote_body = quote.json()["data"]
    quote_id = quote_body["id"]
    assert float(quote_body["tax_amount"]) == pytest.approx(6)
    assert float(quote_body["total_amount"]) == pytest.approx(46)

    order_conv = await ac.post(
        f"/api/v1/sales/quotations/{quote_id}/convert-order", headers=headers
    )
    assert order_conv.status_code == 200, order_conv.text
    order_id = order_conv.json()["data"]["id"]

    confirmed = await ac.post(
        f"/api/v1/sales/orders/{order_id}/confirm", headers=headers
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "confirmed"

    inv_conv = await ac.post(
        f"/api/v1/sales/orders/{order_id}/convert-invoice", headers=headers
    )
    assert inv_conv.status_code == 200, inv_conv.text
    inv_body = inv_conv.json()["data"]
    invoice_id = inv_body["id"]
    assert float(inv_body["tax_amount"]) == pytest.approx(6)
    assert float(inv_body["total_amount"]) == pytest.approx(46)

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] in {"posted", "sent", "unpaid"}

    db_session.expire_all()
    product = (
        await db_session.execute(select(m.Product).where(m.Product.id == product_id))
    ).scalar_one()
    assert float(product.stock_qty) == pytest.approx(opening_stock - 10)

    cust = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert cust.status_code == 200
    assert float(cust.json()["data"]["balance"]) == pytest.approx(balance0 + 46)

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert journals.status_code == 200
    inv_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_invoice" and j.get("source_id") == invoice_id
    ]
    assert len(inv_jes) == 1
    assert float(inv_jes[0]["total_debit"]) == pytest.approx(46)

    pay = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "amount": 46,
            "sales_invoice_id": invoice_id,
            "payment_method": "cash",
            "reference": "C1-AR",
        },
    )
    assert pay.status_code == 200, pay.text

    inv_after = await ac.get(f"/api/v1/sales/invoices/{invoice_id}", headers=headers)
    assert inv_after.status_code == 200
    assert inv_after.json()["data"]["status"] == "paid"
    assert float(inv_after.json()["data"]["paid_amount"]) == pytest.approx(46)

    cust2 = await ac.get(f"/api/v1/customers/{customer_id}", headers=headers)
    assert float(cust2.json()["data"]["balance"]) == pytest.approx(balance0)

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.action.in_(("invoice_posted", "customer_payment")),
            )
        )
    ).scalars().all()
    actions = {a.action for a in audits}
    assert "invoice_posted" in actions
    assert "customer_payment" in actions
