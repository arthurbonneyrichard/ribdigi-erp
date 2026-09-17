"""Sales return OVER_RETURN guard — cumulative qty across draft+posted returns."""

from __future__ import annotations

import pyotp
import pytest

from app import accounting as accounting_svc
from app.inventory import apply_stock_change
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_return_blocks_duplicate_over_return(client, db_session):
    """Second return exceeding remaining invoice qty returns OVER_RETURN (409)."""
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id, company_id=seed["c1"].id)

    store = await create_store(
        db_session,
        tenant_id=tenant_id,
        company_id=seed["c1"].id,
        code="ORWH",
        name="Over-return Store",
    )
    wh = await warehouse_for_store(db_session, tenant_id, store.id)
    product = seed["p1"]
    product.cost_price = 4
    product.stock_qty = 0
    product.reserved_qty = 0
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=20,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=wh.id,
    )
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Over Return Customer", "credit_limit": 10000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "store_id": store.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2,
                    "unit_price": 50,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    first = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["data"]["id"]
    posted_first = await ac.post(f"/api/v1/sales/returns/{first_id}/post", headers=headers)
    assert posted_first.status_code == 200, posted_first.text

    # Remaining qty is 1 — requesting 2 must fail with OVER_RETURN
    blocked = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 2}],
        },
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "OVER_RETURN"
    assert float(detail["available"]) == pytest.approx(1.0)
    assert float(detail["requested"]) == pytest.approx(2.0)

    # Exact remaining qty still allowed
    ok = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text

    # Draft also reserves qty — third return of 1 must fail
    blocked_draft = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert blocked_draft.status_code == 409, blocked_draft.text
    assert blocked_draft.json()["detail"]["code"] == "OVER_RETURN"
