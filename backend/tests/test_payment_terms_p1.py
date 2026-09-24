"""Per-party payment terms drive invoice/PO due dates (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app.credit import DEFAULT_PAYMENT_TERMS_DAYS, default_due_date, party_terms_days
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_party_terms_days_helpers():
    assert party_terms_days(None) == DEFAULT_PAYMENT_TERMS_DAYS
    p = m.Party(name="X", kind="customer", payment_terms_days=45)
    assert party_terms_days(p) == 45
    p0 = m.Party(name="Y", kind="supplier", payment_terms_days=0)
    assert party_terms_days(p0) == 0
    base = datetime(2026, 8, 1, 12, 0, 0)
    assert default_due_date(base, 14) == base + timedelta(days=14)
    assert default_due_date(base, 0) == base


@pytest.mark.asyncio
async def test_customer_create_and_invoice_due_uses_terms(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 50},
    )
    assert stock.status_code == 200, stock.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Net45 Buyer", "credit_limit": 5000, "payment_terms_days": 45},
    )
    assert cust.status_code == 200, cust.text
    data = cust.json()["data"]
    assert data["payment_terms_days"] == 45
    customer_id = data["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    due = posted.json()["data"]["due_date"]
    posted_at = posted.json()["data"]["posted_at"]
    assert due and posted_at
    due_dt = datetime.fromisoformat(due.replace("Z", ""))
    post_dt = datetime.fromisoformat(posted_at.replace("Z", ""))
    assert (due_dt.date() - post_dt.date()).days == 45

    lim = await ac.patch(
        f"/api/v1/customers/{customer_id}/credit-limit",
        headers=headers,
        json={"credit_limit": 6000, "payment_terms_days": 7},
    )
    assert lim.status_code == 200, lim.text
    assert lim.json()["data"]["payment_terms_days"] == 7


@pytest.mark.asyncio
async def test_supplier_terms_on_purchase_invoice(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    supp = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Net60 Vendor", "payment_terms_days": 60},
    )
    assert supp.status_code == 200, supp.text
    assert supp.json()["data"]["payment_terms_days"] == 60
    supplier_id = supp.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/suppliers/{supplier_id}",
        headers=headers,
        json={"payment_terms_days": 21},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["payment_terms_days"] == 21

    pin = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product.id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert pin.status_code == 200, pin.text
    body = pin.json()["data"]
    due = body["due_date"]
    inv_date = body["invoice_date"]
    assert due and inv_date
    due_dt = datetime.fromisoformat(due.replace("Z", ""))
    inv_dt = datetime.fromisoformat(inv_date.replace("Z", ""))
    assert (due_dt.date() - inv_dt.date()).days == 21
