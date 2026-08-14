"""Configurable PO / GRN / quotation numbering (BR-20.4)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app.doc_numbers import next_grn_number
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_quotation_po_grn_numbering(client, db_session, seeded, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    year = datetime.utcnow().year
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")

    sales = await ac.get("/api/v1/sales/settings", headers=admin)
    assert sales.status_code == 200
    assert sales.json()["data"]["quotation_numbering"]["preview"] == f"QT-{year}-0001"

    await ac.patch(
        "/api/v1/sales/settings",
        headers=admin,
        json={"quotation_numbering": {"prefix": "Q", "next_number": 5}},
    )
    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Quote Co", "email": "q@example.com"},
    )
    q = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert q.status_code == 200, q.text
    assert q.json()["data"]["quotation_number"] == f"Q-{year}-0005"

    purch = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=admin,
        json={
            "purchase_order_numbering": {"prefix": "PO", "next_number": 3},
            "grn_numbering": {"prefix": "GRN", "next_number": 9},
        },
    )
    assert purch.status_code == 200, purch.text
    assert purch.json()["data"]["purchase_order_numbering"]["preview"] == f"PO-{year}-0003"
    assert purch.json()["data"]["grn_numbering"]["preview"] == f"GRN-{year}-0009"

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Num Supplier", "kind": "supplier", "email": "sup@example.com"},
    )
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert po.status_code == 200, po.text
    assert po.json()["data"]["po_number"] == f"PO-{year}-0003"

    po_id = po.json()["data"]["id"]
    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    items = sent.json()["data"]["items"]
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=admin,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": items[0]["id"],
                    "received_qty": 2,
                    "accepted_qty": 2,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    assert grn.json()["data"]["grn_number"] == f"GRN-{year}-0009"

    # Purchase invoice numbering (BR-6.5 / BR-20.4)
    purch_pi = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=admin,
        json={"purchase_invoice_numbering": {"prefix": "PINV", "next_number": 7}},
    )
    assert purch_pi.status_code == 200, purch_pi.text
    assert purch_pi.json()["data"]["purchase_invoice_numbering"]["preview"] == f"PINV-{year}-0007"
    get_settings = await ac.get("/api/v1/purchasing/settings", headers=admin)
    assert get_settings.status_code == 200
    assert get_settings.json()["data"]["purchase_invoice_numbering"]["preview"] == f"PINV-{year}-0007"

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    assert inv.json()["data"]["invoice_number"] == f"PINV-{year}-0007"

    # Purchase return + debit note numbering (BR-6.6 / BR-20.4)
    purch_ret = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=admin,
        json={
            "purchase_return_numbering": {"prefix": "PR", "next_number": 4},
            "debit_note_numbering": {"prefix": "DN", "next_number": 6},
        },
    )
    assert purch_ret.status_code == 200, purch_ret.text
    assert purch_ret.json()["data"]["purchase_return_numbering"]["preview"] == f"PR-{year}-0004"
    assert purch_ret.json()["data"]["debit_note_numbering"]["preview"] == f"DN-{year}-0006"

    gitems = grn.json()["data"].get("items") or []
    if not gitems:
        gdetail = await ac.get(f"/api/v1/purchasing/grn/{grn.json()['data']['id']}", headers=admin)
        gitems = gdetail.json()["data"]["items"]
    ret = await ac.post(
        "/api/v1/purchasing/returns",
        headers=admin,
        json={
            "goods_receipt_id": grn.json()["data"]["id"],
            "reason": "damaged",
            "items": [{"goods_receipt_item_id": gitems[0]["id"], "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    assert ret.json()["data"]["return_number"] == f"PR-{year}-0004"
    assert ret.json()["data"].get("debit_note_number") in (None, "")

    posted = await ac.post(
        f"/api/v1/purchasing/returns/{ret.json()['data']['id']}/post",
        headers=admin,
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["debit_note_number"] == f"DN-{year}-0006"
    assert posted.json()["data"]["status"] == "posted"

    # Sales return + credit note numbering (BR-7.5 / BR-20.4)
    sales_num = await ac.patch(
        "/api/v1/sales/settings",
        headers=admin,
        json={
            "sales_return_numbering": {"prefix": "SR", "next_number": 8},
            "credit_note_numbering": {"prefix": "CN", "next_number": 11},
        },
    )
    assert sales_num.status_code == 200, sales_num.text
    assert sales_num.json()["data"]["sales_return_numbering"]["preview"] == f"SR-{year}-0008"
    assert sales_num.json()["data"]["credit_note_numbering"]["preview"] == f"CN-{year}-0011"

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "SR Num Co", "email": "srnum@example.com"},
    )
    assert cust.status_code == 200, cust.text
    sinv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 20}],
        },
    )
    assert sinv.status_code == 200, sinv.text
    sinv_id = sinv.json()["data"]["id"]
    sinv_posted = await ac.post(f"/api/v1/sales/invoices/{sinv_id}/post", headers=admin)
    assert sinv_posted.status_code == 200, sinv_posted.text
    from app import models as m

    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(product.stock_qty or 0) + 5
    await db_session.commit()

    sret = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": sinv_id,
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sret.status_code == 200, sret.text
    assert sret.json()["data"]["return_number"] == f"SR-{year}-0008"
    sposted = await ac.post(
        f"/api/v1/sales/returns/{sret.json()['data']['id']}/post",
        headers=admin,
        json={"settlement_method": "adjust"},
    )
    assert sposted.status_code == 200, sposted.text
    assert sposted.json()["data"]["credit_note_number"] == f"CN-{year}-0011"

    # Sales order numbering (BR-7.3 / BR-20.4)
    so_settings = await ac.patch(
        "/api/v1/sales/settings",
        headers=admin,
        json={"sales_order_numbering": {"prefix": "SO", "next_number": 12}},
    )
    assert so_settings.status_code == 200, so_settings.text
    assert so_settings.json()["data"]["sales_order_numbering"]["preview"] == f"SO-{year}-0012"
    so = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 15}],
        },
    )
    assert so.status_code == 200, so.text
    assert so.json()["data"]["order_number"] == f"SO-{year}-0012"

    # Purchase request numbering (BR-6.2 / BR-20.4)
    preq_settings = await ac.patch(
        "/api/v1/purchasing/settings",
        headers=admin,
        json={"purchase_request_numbering": {"prefix": "PREQ", "next_number": 3}},
    )
    assert preq_settings.status_code == 200, preq_settings.text
    assert preq_settings.json()["data"]["purchase_request_numbering"]["preview"] == f"PREQ-{year}-0003"
    preq = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
        },
    )
    assert preq.status_code == 200, preq.text
    assert preq.json()["data"]["request_number"] == f"PREQ-{year}-0003"

    # Counter advanced for next GRN
    assert await next_grn_number(db_session, seed["t1"].id) == f"GRN-{year}-0010"
    await db_session.commit()
