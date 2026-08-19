"""Stage 19 S1: Sales + Purchases API fidelity (BR-18.4–18.5)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.inventory import apply_stock_change
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_purchases_api_br_18_5_jwt(client, db_session):
    """BR-18.5: suppliers, PR→PO, GRN, purchase invoice, supplier payment via JWT."""
    ac, seed = client
    headers = await _mgr(ac)
    admin = await _admin(ac, seed)
    product_id = seed["p1"].id

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "S19 S1 Supplier", "code": "S19-S1-SUP"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/suppliers/{supplier_id}",
        headers=headers,
        json={"notes": "Stage 19 S1"},
    )
    assert patched.status_code == 200, patched.text

    listed = await ac.get("/api/v1/suppliers", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(s["id"] == supplier_id for s in listed.json()["data"])

    pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 4, "unit_price": 5}],
        },
    )
    assert pr.status_code == 200, pr.text
    pr_id = pr.json()["data"]["id"]
    submitted = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    approved = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=admin)
    assert approved.status_code == 200, approved.text
    converted = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/convert", headers=headers)
    assert converted.status_code == 200, converted.text
    assert converted.json()["data"]["purchase_order"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": 6, "unit_price": 5}],
        },
    )
    assert po.status_code == 200, po.text
    po_body = po.json()["data"]
    po_id = po_body["id"]
    po_item_id = po_body["items"][0]["id"]

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 6,
                    "accepted_qty": 6,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"goods_receipt_id": grn_id},
    )
    assert inv.status_code == 200, inv.text
    inv_id = inv.json()["data"]["id"]
    inv_total = float(inv.json()["data"]["total_amount"])

    appr = await ac.post(f"/api/v1/purchasing/invoices/{inv_id}/approve", headers=headers)
    assert appr.status_code == 200, appr.text

    pay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "amount": inv_total,
            "purchase_invoice_id": inv_id,
            "payment_method": "bank_transfer",
            "reference": "S19-S1-AP",
        },
    )
    assert pay.status_code == 200, pay.text


@pytest.mark.asyncio
async def test_sales_api_br_18_4_thin_regression(client, db_session):
    """BR-18.4 thin JWT regression: quote→order→invoice→payment + POS sale."""
    ac, seed = client
    headers = await _mgr(ac)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    tenant_id = seed["t1"].id

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=30,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "S19 S1 Customer",
            "party_type": "registered",
            "credit_limit": 2000,
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 2, "unit_price": 10}],
        },
    )
    assert quote.status_code == 200, quote.text
    quote_id = quote.json()["data"]["id"]

    order_conv = await ac.post(
        f"/api/v1/sales/quotations/{quote_id}/convert-order", headers=headers
    )
    assert order_conv.status_code == 200, order_conv.text
    order_id = order_conv.json()["data"]["id"]

    confirmed = await ac.post(f"/api/v1/sales/orders/{order_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    inv_conv = await ac.post(
        f"/api/v1/sales/orders/{order_id}/convert-invoice", headers=headers
    )
    assert inv_conv.status_code == 200, inv_conv.text
    invoice_id = inv_conv.json()["data"]["id"]
    inv_total = float(inv_conv.json()["data"]["total_amount"])

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    pay = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "amount": inv_total,
            "sales_invoice_id": invoice_id,
            "payment_method": "cash",
            "reference": "S19-S1-AR",
        },
    )
    assert pay.status_code == 200, pay.text

    # Sales return create (post covered heavily by Stage 15 R1)
    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "other",
            "restock": True,
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text


@pytest.mark.asyncio
async def test_api_key_read_sales_and_purchasing(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/api-keys",
        headers=admin,
        json={
            "name": "Stage19 S1 reader",
            "permissions": {"sales": ["read"], "purchasing": ["read"]},
        },
    )
    assert created.status_code == 200, created.text
    secret = created.json()["data"]["api_key"]
    key_headers = {"X-API-Key": secret, "X-Tenant-ID": seed["t1"].id}

    quotes = await ac.get("/api/v1/sales/quotations", headers=key_headers)
    assert quotes.status_code == 200, quotes.text

    suppliers = await ac.get("/api/v1/suppliers", headers=key_headers)
    assert suppliers.status_code == 200, suppliers.text

    orders = await ac.get("/api/v1/purchasing/orders", headers=key_headers)
    assert orders.status_code == 200, orders.text

    denied = await ac.post(
        "/api/v1/suppliers",
        headers=key_headers,
        json={"name": "Denied"},
    )
    assert denied.status_code == 403


def test_br_18_4_18_5_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    p18_4 = br.split("#### BR-18.4 Sales API")[1].split("#### BR-18.5")[0]
    assert "[x] Create quotations, sales orders, invoices" in p18_4
    assert "[x] Record payments" in p18_4
    assert "[x] Sales return processing" in p18_4
    assert "[x] POS transaction submission" in p18_4
    assert "Stage 19 S1" in p18_4

    p18_5 = br.split("#### BR-18.5 Purchases API")[1].split("#### BR-18.6")[0]
    assert "[x] Create purchase requests, orders, GRNs, invoices" in p18_5
    assert "[x] Supplier management" in p18_5
    assert "[x] Payment recording" in p18_5
    assert "Stage 19 S1" in p18_5

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    s1_line = [ln for ln in plan.splitlines() if "| **S1**" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_sales_purchases_api_s1.py" in plan
