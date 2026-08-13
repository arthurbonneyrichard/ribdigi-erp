"""Purchase order / invoice tax auto-resolve (BR-12.2)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_rates_and_product(db_session, seed):
    tenant_id = seed["t1"].id
    default = m.TaxRate(
        tenant_id=tenant_id,
        name="VAT 15",
        rate=15,
        tax_type="VAT",
        is_default=True,
        is_active=True,
    )
    cat_rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Cat 10",
        rate=10,
        tax_type="VAT",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([default, cat_rate])
    await db_session.flush()
    cat = m.ProductCategory(
        tenant_id=tenant_id,
        code="PTAX",
        name="Purchase Tax Cat",
        tax_rate_id=cat_rate.id,
        is_active=True,
    )
    db_session.add(cat)
    await db_session.flush()
    product = seed["p1"]
    product.category_id = cat.id
    product.tax_rate_id = None
    product.tax_supply_class = "standard"
    product.cost_price = 100
    await db_session.commit()
    return product, default, cat_rate


@pytest.mark.asyncio
async def test_po_and_invoice_resolve_omitted_tax_rate(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product, _default, cat_rate = await _seed_rates_and_product(db_session, seed)

    suppliers = await ac.get("/api/v1/suppliers", headers=headers)
    assert suppliers.status_code == 200
    supplier_id = suppliers.json()["data"][0]["id"] if suppliers.json()["data"] else None
    if not supplier_id:
        created = await ac.post(
            "/api/v1/suppliers",
            headers=headers,
            json={"name": "Tax Supplier", "credit_limit": 0},
        )
        assert created.status_code == 200, created.text
        supplier_id = created.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2,
                    "unit_price": 100,
                    # tax_rate omitted → category 10%
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    assert abs(float(po_data["tax_amount"]) - 20) < 0.01  # 200 * 10%
    assert abs(float(po_data["total_amount"]) - 220) < 0.01
    line = po_data["items"][0] if po_data.get("items") else None
    if line is None:
        detail = await ac.get(f"/api/v1/purchasing/orders/{po_data['id']}", headers=headers)
        assert detail.status_code == 200
        line = detail.json()["data"]["items"][0]
    assert abs(float(line["tax_rate"]) - 10) < 0.01

    # Explicit 0 wins over category
    po0 = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": 100,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert po0.status_code == 200, po0.text
    assert abs(float(po0.json()["data"]["tax_amount"])) < 0.01

    # Manual PI omitted rate → category 10%
    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1,
                    "unit_price": 50,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    inv_data = inv.json()["data"]
    assert abs(float(inv_data["tax_amount"]) - 5) < 0.01
    assert abs(float(inv_data["total_amount"]) - 55) < 0.01

    # Product tax_rate_id wins over category
    prod_rate = m.TaxRate(
        tenant_id=seed["t1"].id,
        name="Product 12",
        rate=12,
        tax_type="VAT",
        is_default=False,
        is_active=True,
    )
    db_session.add(prod_rate)
    await db_session.flush()
    product.tax_rate_id = prod_rate.id
    await db_session.commit()

    po_prod = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {"product_id": product.id, "quantity": 1, "unit_price": 100}
            ],
        },
    )
    assert po_prod.status_code == 200, po_prod.text
    assert abs(float(po_prod.json()["data"]["tax_amount"]) - 12) < 0.01
    assert cat_rate.rate == 10  # sanity: category still 10, product won
