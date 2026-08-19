"""BR-6.3 PO delivery address and line tax/discount."""

from __future__ import annotations

import pytest

from app.purchasing import _calc_po_line_amounts, render_po_text
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_po_line_amounts_tax_on_net_after_discount():
    # 10 × 5 = 50, discount 10 → net 40, tax 15% → 6, total 46
    sub, tax, total, disc = _calc_po_line_amounts(10, 5, 15, 10)
    assert disc == 10
    assert sub == 40
    assert tax == 6
    assert total == 46

    with pytest.raises(Exception) as exc:
        _calc_po_line_amounts(2, 5, 0, 20)
    assert exc.value.status_code == 400


def test_render_po_text_includes_delivery_and_discount():
    text = render_po_text(
        {
            "po_number": "PO-1",
            "status": "sent",
            "delivery_address": "12 Warehouse Rd",
            "subtotal": 40,
            "tax_amount": 6,
            "total_amount": 46,
            "items": [
                {
                    "product_id": "prod-1",
                    "quantity": 10,
                    "unit_price": 5,
                    "discount": 10,
                    "line_total": 46,
                }
            ],
        },
        supplier_name="Acme Supply",
        company_name="Alpha Co",
    )
    assert "Deliver to: 12 Warehouse Rd" in text
    assert "10.00" in text  # discount column
    assert "Subtotal: 40.00" in text
    assert "Tax: 6.00" in text


@pytest.mark.asyncio
async def test_create_print_amend_po_delivery_and_discount(client):
    ac, seed = client
    headers = await _mgr(ac)
    product_id = str(seed["p1"].id)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Delivery Sup", "email": "po-disc@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "delivery_address": "Gate B, Industrial Area",
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
    data = created.json()["data"]
    assert data["delivery_address"] == "Gate B, Industrial Area"
    assert data["subtotal"] == 40.0
    assert data["tax_amount"] == 6.0
    assert data["total_amount"] == 46.0
    assert data["items"][0]["discount"] == 10.0
    assert data["items"][0]["tax_rate"] == 15.0
    po_id = data["id"]
    line_id = data["items"][0]["id"]

    printed = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print", headers=headers)
    assert printed.status_code == 200, printed.text
    text = printed.json()["data"]["text"]
    assert "Gate B, Industrial Area" in text
    assert data["po_number"] in text

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=headers,
        json={
            "reason": "Update delivery and discount",
            "delivery_address": "Dock 3, Main Yard",
            "items": [
                {
                    "id": line_id,
                    "product_id": product_id,
                    "quantity": 10,
                    "unit_price": 5,
                    "tax_rate": 15,
                    "discount": 5,
                }
            ],
        },
    )
    assert amended.status_code == 200, amended.text
    amd = amended.json()["data"]
    assert amd["delivery_address"] == "Dock 3, Main Yard"
    assert amd["revision"] == 2
    # net 45, tax 6.75, total 51.75
    assert amd["subtotal"] == 45.0
    assert amd["tax_amount"] == 6.75
    assert amd["total_amount"] == 51.75
    assert amd["items"][0]["discount"] == 5.0

    history = await ac.get(f"/api/v1/purchasing/orders/{po_id}/amendments", headers=headers)
    assert history.status_code == 200
    row = history.json()["data"][0]
    assert row["changes"]["before"]["header"]["delivery_address"] == "Gate B, Industrial Area"
    assert row["changes"]["after"]["header"]["delivery_address"] == "Dock 3, Main Yard"
    assert row["changes"]["before"]["items"][0]["discount"] == 10.0
    assert row["changes"]["after"]["items"][0]["discount"] == 5.0

    bad = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "unit_price": 5,
                    "discount": 10,
                }
            ],
        },
    )
    assert bad.status_code == 400
