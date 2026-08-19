"""Stage 10 T1: product-category tax rules (BR-12.1)."""

from __future__ import annotations

import pytest

from app import models as m
from app.tax import resolve_product_tax
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_category_tax_resolution_precedence(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    default = m.TaxRate(
        tenant_id=tenant_id,
        name="Default VAT",
        rate=10,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=True,
        is_active=True,
    )
    cat_rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Category VAT",
        rate=15,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=False,
        is_active=True,
    )
    prod_rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Product VAT",
        rate=5,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([default, cat_rate, prod_rate])
    await db_session.flush()

    parent = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "T1P", "name": "T1 Parent", "tax_rate_id": cat_rate.id},
    )
    assert parent.status_code == 200, parent.text
    assert parent.json()["data"]["tax_rate_id"] == cat_rate.id
    parent_id = parent.json()["data"]["id"]

    child = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "T1C", "name": "T1 Child", "parent_id": parent_id},
    )
    assert child.status_code == 200, child.text
    child_id = child.json()["data"]["id"]
    assert child.json()["data"]["tax_rate_id"] is None

    product = seed["p1"]
    product.category_id = child_id
    product.tax_rate_id = None
    product.tax_exempt = False
    await db_session.commit()

    # Inherit from parent category when child has no rate
    spec = await resolve_product_tax(db_session, tenant_id, product)
    assert spec.rate_pct == pytest.approx(15.0)

    # Product override wins
    product.tax_rate_id = prod_rate.id
    await db_session.commit()
    spec = await resolve_product_tax(db_session, tenant_id, product)
    assert spec.rate_pct == pytest.approx(5.0)

    # Exempt wins over category/product rates
    product.tax_exempt = True
    await db_session.commit()
    spec = await resolve_product_tax(db_session, tenant_id, product)
    assert spec.rate_pct == pytest.approx(0.0)
    assert spec.supply_category == "exempt"


@pytest.mark.asyncio
async def test_category_tax_patch_and_foreign_rate_rejected(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Patch VAT",
        rate=12,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=False,
        is_active=True,
    )
    foreign = m.TaxRate(
        tenant_id=seed["t2"].id,
        name="Beta VAT",
        rate=20,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([rate, foreign])
    await db_session.commit()

    created = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "T1X", "name": "T1 Patch Cat"},
    )
    assert created.status_code == 200, created.text
    cat_id = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"tax_rate_id": rate.id},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["tax_rate_id"] == rate.id

    bad = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"tax_rate_id": foreign.id},
    )
    assert bad.status_code == 404

    cleared = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"tax_rate_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["tax_rate_id"] is None
