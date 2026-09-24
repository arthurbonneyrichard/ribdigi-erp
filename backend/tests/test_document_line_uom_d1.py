"""PO/GRN/sales line alternate UoM (BR-5.1 document lines)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _case_product(ac, headers):
    units = await ac.get("/api/v1/catalog/units", headers=headers)
    assert units.status_code == 200, units.text
    by_code = {u["code"]: u for u in units.json()["data"]}
    pcs_id = by_code["PCS"]["id"]
    box = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": "CASE12",
            "name": "Case of 12",
            "base_unit_id": pcs_id,
            "conversion_ratio": 12,
        },
    )
    assert box.status_code == 200, box.text
    box_id = box.json()["data"]["id"]
    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Case Widget",
            "sku": "CASE-W-1",
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
            "unit_id": pcs_id,
        },
    )
    assert prod.status_code == 200, prod.text
    return pcs_id, box_id, prod.json()["data"]["id"], by_code


@pytest.mark.asyncio
async def test_po_grn_converts_case_to_pcs(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    _pcs_id, box_id, pid, _by_code = await _case_product(ac, headers)

    # Seed a supplier
    sup = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Case Supplier", "email": "case@supplier.example.com"},
    )
    assert sup.status_code == 200, sup.text
    supplier_id = sup.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": pid,
                    "quantity": 2,
                    "unit_id": box_id,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    assert po_data["items"][0]["unit_id"] == box_id
    assert po_data["items"][0]["quantity"] == 2.0
    po_item_id = po_data["items"][0]["id"]

    # Mark sent without relying on SMTP (console email still needs recipient — already set)
    sent = await ac.post(f"/api/v1/purchasing/orders/{po_data['id']}/send", headers=headers)
    if sent.status_code != 200:
        from app import models as m

        row = await db_session.get(m.PurchaseOrder, po_data["id"])
        row.status = "sent"
        await db_session.commit()

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_data["id"],
            "items": [{"po_item_id": po_item_id, "received_qty": 2, "accepted_qty": 2}],
        },
    )
    assert grn.status_code == 200, grn.text
    assert grn.json()["data"]["items"][0]["unit_id"] == box_id

    product = await ac.get(f"/api/v1/products/{pid}", headers=headers)
    assert product.status_code == 200, product.text
    assert float(product.json()["data"]["stock_qty"]) == 24.0


@pytest.mark.asyncio
async def test_sales_invoice_post_converts_case_to_pcs(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    _pcs_id, box_id, pid, _by_code = await _case_product(ac, headers)

    # Stock in 24 pcs first
    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": pid, "quantity": 24},
    )
    assert stock.status_code == 200, stock.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Case Buyer", "credit_limit": 10000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": pid,
                    "quantity": 1,
                    "unit_id": box_id,
                    "unit_price": 20,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    assert inv.json()["data"]["items"][0]["unit_id"] == box_id
    invoice_id = inv.json()["data"]["id"]

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    product = await ac.get(f"/api/v1/products/{pid}", headers=headers)
    assert float(product.json()["data"]["stock_qty"]) == 12.0


@pytest.mark.asyncio
async def test_incompatible_line_unit_rejected(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    _pcs_id, _box_id, pid, by_code = await _case_product(ac, headers)
    kg_id = by_code["KG"]["id"]

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Bad Unit Buyer"},
    )
    assert cust.status_code == 200, cust.text

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": pid, "quantity": 1, "unit_id": kg_id, "unit_price": 1}],
        },
    )
    assert inv.status_code == 400, inv.text


@pytest.mark.asyncio
async def test_default_line_without_unit_id_unchanged(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    units = await ac.get("/api/v1/catalog/units", headers=headers)
    pcs_id = next(u["id"] for u in units.json()["data"] if u["code"] == "PCS")
    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Plain Widget",
            "sku": "PLAIN-1",
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 10,
            "unit_id": pcs_id,
        },
    )
    assert prod.status_code == 200, prod.text
    pid = prod.json()["data"]["id"]

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Plain Buyer", "credit_limit": 1000},
    )
    customer_id = cust.json()["data"]["id"]
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": pid, "quantity": 3, "unit_price": 2}],
        },
    )
    assert inv.status_code == 200, inv.text
    posted = await ac.post(
        f"/api/v1/sales/invoices/{inv.json()['data']['id']}/post", headers=headers
    )
    assert posted.status_code == 200, posted.text
    product = await ac.get(f"/api/v1/products/{pid}", headers=headers)
    assert float(product.json()["data"]["stock_qty"]) == 7.0
