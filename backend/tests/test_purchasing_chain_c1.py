"""Stage 11 C1: PO → GRN → inventory → supplier balance → accounting → payment chain."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.purchasing import _calc_partial_po_line_amounts, _calc_po_line_amounts
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_partial_po_line_scales_discount():
    # Full: 10 × 5 = 50, discount 10 → net 40, tax 15% → 6, total 46
    assert _calc_po_line_amounts(10, 5, 15, 10)[2] == 46
    # Half qty → half discount (5) → net 20, tax 3, total 23
    sub, tax, total, disc = _calc_partial_po_line_amounts(5, 5, 15, 10, 10)
    assert disc == 5
    assert sub == 20
    assert tax == 3
    assert total == 23


@pytest.mark.asyncio
async def test_po_grn_inventory_balance_journal_invoice_payment(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = seed["p1"]
    product.stock_qty = 0
    await db_session.commit()
    opening_stock = 0.0

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Chain Sup C1"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    assert float(supplier.json()["data"]["balance"] or 0) == 0

    # PO: 10 @ 5, discount 10, tax 15% → total 46
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 10,
                    "unit_price": 5,
                    "tax_rate": 15,
                    "discount": 10,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_body = po.json()["data"]
    po_id = po_body["id"]
    po_item_id = po_body["items"][0]["id"]
    assert float(po_body["total_amount"]) == pytest.approx(46)

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    # Sent but not received — AP aging must not use full PO total
    aging_pre = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert aging_pre.status_code == 200, aging_pre.text
    pre_docs = [
        d
        for d in aging_pre.json()["data"]["documents"]
        if d.get("id") == po_id or d.get("document_number") == po_body["po_number"]
    ]
    assert pre_docs == []

    # Partial GRN: accept 5 → expected value 23
    expected_grn_value = _calc_partial_po_line_amounts(5, 5, 15, 10, 10)[2]
    assert expected_grn_value == 23

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 5,
                    "accepted_qty": 5,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]

    prod = await ac.get(f"/api/v1/products/{product.id}", headers=headers)
    assert prod.status_code == 200
    assert float(prod.json()["data"]["stock_qty"]) == pytest.approx(opening_stock + 5)

    sup = await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)
    assert sup.status_code == 200
    assert float(sup.json()["data"]["balance"]) == pytest.approx(expected_grn_value)

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert journals.status_code == 200
    grn_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "grn" and j.get("source_id") == grn_id
    ]
    assert len(grn_jes) == 1
    assert float(grn_jes[0]["total_debit"]) == pytest.approx(expected_grn_value)

    aging = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert aging.status_code == 200
    po_docs = [d for d in aging.json()["data"]["documents"] if d.get("id") == po_id]
    assert len(po_docs) == 1
    assert float(po_docs[0]["balance_due"]) == pytest.approx(expected_grn_value)
    assert float(po_docs[0]["balance_due"]) < float(po_body["total_amount"])

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"goods_receipt_id": grn_id},
    )
    assert inv.status_code == 200, inv.text
    inv_body = inv.json()["data"]
    inv_id = inv_body["id"]
    assert float(inv_body["total_amount"]) == pytest.approx(expected_grn_value)
    assert inv_body.get("ap_posted") is False

    balance_before_approve = float(
        (await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)).json()["data"][
            "balance"
        ]
    )

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv_id}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    appr = approved.json()["data"]
    assert appr.get("ap_posted") is False
    assert float(appr["total_amount"]) == pytest.approx(expected_grn_value)

    balance_after_approve = float(
        (await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)).json()["data"][
            "balance"
        ]
    )
    assert balance_after_approve == pytest.approx(balance_before_approve)

    # No second Inv/AP journal for GRN-linked PI
    journals2 = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    pi_jes = [
        j
        for j in journals2.json()["data"]
        if j.get("source_type") == "purchase_invoice" and j.get("source_id") == inv_id
    ]
    assert pi_jes == []

    pay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "amount": expected_grn_value,
            "purchase_invoice_id": inv_id,
            "payment_method": "bank_transfer",
            "reference": "C1-PAY",
        },
    )
    assert pay.status_code == 200, pay.text

    balance_paid = float(
        (await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)).json()["data"][
            "balance"
        ]
    )
    assert balance_paid == pytest.approx(0)

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action.in_(("po_created", "po_sent", "grn_posted")),
            )
        )
    ).scalars().all()
    actions = {a.action for a in audits}
    assert "po_created" in actions
    assert "po_sent" in actions
    assert "grn_posted" in actions
