"""Stage 15 I1: standard-cost COGS 5000 + Inventory 1200 on sale and return reverse."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app.inventory import apply_stock_change
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
        code = code_by_id[ln["account_id"]]
        by_code.setdefault(code, []).append(ln)
    return by_code


@pytest.mark.asyncio
async def test_invoice_posts_cogs_and_inventory_gl(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.cost_price = 3.5
    product.stock_qty = 50
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    inv_acct = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == tenant_id, m.Account.code == "1200"
            )
        )
    ).scalar_one()
    cogs_acct = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == tenant_id, m.Account.code == "5000"
            )
        )
    ).scalar_one()
    inv_before = float(inv_acct.balance or 0)
    cogs_before = float(cogs_acct.balance or 0)

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "I1 COGS Customer", "credit_limit": 5000},
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
                    "product_id": product.id,
                    "quantity": 4,
                    "unit_price": 20,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    inv_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_invoice" and j.get("source_id") == invoice_id
    ]
    assert len(inv_jes) == 1
    expected_cogs = 14.0  # 4 × 3.5
    # AR 80 + COGS 14
    assert float(inv_jes[0]["total_debit"]) == pytest.approx(80 + expected_cogs)

    detail = await ac.get(
        f"/api/v1/accounting/journal-entries/{inv_jes[0]['id']}", headers=headers
    )
    by_code = await _codes_by_account(db_session, tenant_id, detail.json()["data"]["lines"])
    assert sum(float(ln["debit"]) for ln in by_code["5000"]) == pytest.approx(expected_cogs)
    assert sum(float(ln["credit"]) for ln in by_code["1200"]) == pytest.approx(expected_cogs)
    assert "1100" in by_code and "4000" in by_code

    await db_session.refresh(inv_acct)
    await db_session.refresh(cogs_acct)
    # Inventory asset natural debit → credit decreases balance
    assert float(inv_acct.balance or 0) == pytest.approx(inv_before - expected_cogs)
    assert float(cogs_acct.balance or 0) == pytest.approx(cogs_before + expected_cogs)

    pl = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=headers,
        params={"from_date": "2000-01-01", "to_date": "2099-12-31"},
    )
    assert pl.status_code == 200, pl.text
    assert float(pl.json()["data"]["cogs"]) >= expected_cogs


@pytest.mark.asyncio
async def test_return_restock_reverses_cogs_inventory(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.cost_price = 5
    product.stock_qty = 30
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=20,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "I1 Return Customer", "credit_limit": 5000},
    )
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product.id, "quantity": 2, "unit_price": 25, "tax_rate": 0}
            ],
        },
    )
    invoice_id = inv.json()["data"]["id"]
    assert (
        await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    ).status_code == 200

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "defective",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    return_id = ret.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/returns/{return_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    ret_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_return" and j.get("source_id") == return_id
    ]
    assert len(ret_jes) == 1
    detail = await ac.get(
        f"/api/v1/accounting/journal-entries/{ret_jes[0]['id']}", headers=headers
    )
    by_code = await _codes_by_account(db_session, tenant_id, detail.json()["data"]["lines"])
    assert sum(float(ln["debit"]) for ln in by_code["1200"]) == pytest.approx(5)
    assert sum(float(ln["credit"]) for ln in by_code["5000"]) == pytest.approx(5)


@pytest.mark.asyncio
async def test_zero_cost_skips_cogs_lines(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.cost_price = 0
    product.stock_qty = 20
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "I1 Zero Cost", "credit_limit": 1000},
    )
    customer_id = cust.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product.id, "quantity": 1, "unit_price": 10, "tax_rate": 0}
            ],
        },
    )
    invoice_id = created.json()["data"]["id"]
    assert (
        await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    ).status_code == 200

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    inv_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_invoice" and j.get("source_id") == invoice_id
    ]
    assert float(inv_jes[0]["total_debit"]) == pytest.approx(10)
    detail = await ac.get(
        f"/api/v1/accounting/journal-entries/{inv_jes[0]['id']}", headers=headers
    )
    by_code = await _codes_by_account(db_session, tenant_id, detail.json()["data"]["lines"])
    assert "5000" not in by_code
    assert "1200" not in by_code
