"""Product-category-specific tax rules (BR-12.1 / BR-2.8)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.tax import resolve_product_tax
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_resolve_uses_category_then_parent_then_default(db_session, seeded):
    tenant_id = seeded["t1"].id
    default = m.TaxRate(
        tenant_id=tenant_id,
        name="VAT 15",
        rate=15,
        tax_type="VAT",
        is_default=True,
        is_active=True,
    )
    bev_rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Beverage 10",
        rate=10,
        tax_type="VAT",
        is_default=False,
        is_active=True,
    )
    soda_rate = m.TaxRate(
        tenant_id=tenant_id,
        name="Soda 12",
        rate=12,
        tax_type="VAT",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([default, bev_rate, soda_rate])
    await db_session.flush()

    parent = m.ProductCategory(
        tenant_id=tenant_id,
        code="BEV",
        name="Beverages",
        tax_rate_id=bev_rate.id,
        is_active=True,
    )
    db_session.add(parent)
    await db_session.flush()
    child = m.ProductCategory(
        tenant_id=tenant_id,
        code="SODA",
        name="Sodas",
        parent_id=parent.id,
        tax_rate_id=None,
        is_active=True,
    )
    db_session.add(child)
    await db_session.flush()

    # No product rate, child inherits parent category rate
    p_inherit = m.Product(
        tenant_id=tenant_id,
        name="Cola",
        sku="CAT-TAX-1",
        selling_price=10,
        category_id=child.id,
        tax_rate_id=None,
        tax_supply_class="standard",
    )
    # Product rate wins over category
    p_product = m.Product(
        tenant_id=tenant_id,
        name="Premium Cola",
        sku="CAT-TAX-2",
        selling_price=10,
        category_id=child.id,
        tax_rate_id=soda_rate.id,
        tax_supply_class="standard",
    )
    # No category → tenant default
    p_default = m.Product(
        tenant_id=tenant_id,
        name="Misc",
        sku="CAT-TAX-3",
        selling_price=10,
        category_id=None,
        tax_rate_id=None,
        tax_supply_class="standard",
    )
    db_session.add_all([p_inherit, p_product, p_default])
    await db_session.commit()

    inherit = await resolve_product_tax(db_session, tenant_id, p_inherit)
    assert inherit.rate_pct == 10
    assert inherit.tax_rate_id == bev_rate.id

    product_wins = await resolve_product_tax(db_session, tenant_id, p_product)
    assert product_wins.rate_pct == 12
    assert product_wins.tax_rate_id == soda_rate.id

    fallback = await resolve_product_tax(db_session, tenant_id, p_default)
    assert fallback.rate_pct == 15
    assert fallback.tax_rate_id == default.id

    # Child with own rate overrides parent
    child.tax_rate_id = soda_rate.id
    await db_session.commit()
    own = await resolve_product_tax(db_session, tenant_id, p_inherit)
    assert own.rate_pct == 12


@pytest.mark.asyncio
async def test_category_api_assign_and_clear_tax_rate(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    rate = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": "Cat VAT 8", "rate": 8, "tax_type": "vat"},
    )
    assert rate.status_code == 200, rate.text
    rate_id = rate.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "TXCAT", "name": "Taxed Cat", "tax_rate_id": rate_id},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["tax_rate_id"] == rate_id
    cat_id = created.json()["data"]["id"]

    cleared = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"tax_rate_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["tax_rate_id"] is None

    foreign = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"tax_rate_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert foreign.status_code == 404
