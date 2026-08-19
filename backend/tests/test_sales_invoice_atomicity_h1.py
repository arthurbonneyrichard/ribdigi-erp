"""Stage 15 H1: invoice post atomicity — stock-fail leaves draft, no AR/JE/movements."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _snapshot(db, tenant_id: str, *, invoice_id: str, customer_id: str, product_id: str):
    db.expire_all()
    invoice = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.id == invoice_id,
                m.SalesInvoice.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    customer = (
        await db.execute(
            select(m.Party).where(m.Party.id == customer_id, m.Party.tenant_id == tenant_id)
        )
    ).scalar_one()
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one()
    je_n = (
        await db.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "sales_invoice",
                m.JournalEntry.source_id == invoice_id,
            )
        )
    ).scalar_one()
    mv_n = (
        await db.execute(
            select(func.count())
            .select_from(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.reference_type == "sales_invoice",
                m.StockMovement.reference_id == invoice_id,
            )
        )
    ).scalar_one()
    return {
        "status": invoice.status,
        "balance": float(customer.balance or 0),
        "stock": float(product.stock_qty or 0),
        "je": int(je_n),
        "mv": int(mv_n),
    }


@pytest.mark.asyncio
async def test_invoice_post_insufficient_stock_no_orphans(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.stock_qty = 1
    product.reserved_qty = 0
    product.cost_price = 2
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "H1 Atomic Customer", "credit_limit": 5000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]
    balance0 = float(cust.json()["data"].get("balance") or 0)

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 5,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    before = await _snapshot(
        db_session,
        tenant_id,
        invoice_id=invoice_id,
        customer_id=customer_id,
        product_id=product.id,
    )
    assert before["status"] == "draft"
    assert before["je"] == 0
    assert before["mv"] == 0

    denied = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert denied.status_code == 409, denied.text
    detail = denied.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_STOCK"
    assert float(detail["available"]) == pytest.approx(1)
    assert float(detail["requested"]) == pytest.approx(5)

    await db_session.commit()
    after = await _snapshot(
        db_session,
        tenant_id,
        invoice_id=invoice_id,
        customer_id=customer_id,
        product_id=product.id,
    )
    assert after["status"] == "draft"
    assert after["balance"] == pytest.approx(balance0)
    assert after["stock"] == pytest.approx(1)
    assert after["je"] == 0
    assert after["mv"] == 0


@pytest.mark.asyncio
async def test_invoice_post_aggregated_lines_reject_before_partial(client, db_session):
    """Two lines of 1 each against stock 1 must fail aggregated preflight."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.stock_qty = 1
    product.reserved_qty = 0
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "H1 Aggregate Customer", "credit_limit": 5000},
    )
    customer_id = cust.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product.id, "quantity": 1, "unit_price": 8, "tax_rate": 0},
                {"product_id": product.id, "quantity": 1, "unit_price": 8, "tax_rate": 0},
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]

    denied = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"]["code"] == "INSUFFICIENT_STOCK"
    assert float(denied.json()["detail"]["requested"]) == pytest.approx(2)

    await db_session.commit()
    after = await _snapshot(
        db_session,
        tenant_id,
        invoice_id=invoice_id,
        customer_id=customer_id,
        product_id=product.id,
    )
    assert after["status"] == "draft"
    assert after["stock"] == pytest.approx(1)
    assert after["je"] == 0
    assert after["mv"] == 0


@pytest.mark.asyncio
async def test_invoice_post_success_still_commits_stock_ar_journal(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.stock_qty = 10
    product.reserved_qty = 0
    product.cost_price = 1
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "H1 Success Customer", "credit_limit": 5000},
    )
    customer_id = cust.json()["data"]["id"]
    balance0 = float(cust.json()["data"].get("balance") or 0)

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product.id, "quantity": 2, "unit_price": 15, "tax_rate": 0}
            ],
        },
    )
    invoice_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] in {"posted", "sent", "unpaid"}

    await db_session.commit()
    after = await _snapshot(
        db_session,
        tenant_id,
        invoice_id=invoice_id,
        customer_id=customer_id,
        product_id=product.id,
    )
    assert after["status"] == "posted"
    assert after["balance"] == pytest.approx(balance0 + 30)
    assert after["stock"] == pytest.approx(8)
    assert after["je"] == 1
    assert after["mv"] >= 1
