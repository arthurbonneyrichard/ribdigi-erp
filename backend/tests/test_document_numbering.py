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

    # Counter advanced for next GRN
    assert await next_grn_number(db_session, seed["t1"].id) == f"GRN-{year}-0010"
    await db_session.commit()
