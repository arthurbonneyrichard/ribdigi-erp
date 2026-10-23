"""POS search: a plain word like "sugar" must search names, not only exact barcodes."""

import pytest

from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_pos_search_word_falls_back_to_name(client, db_session, seeded):
    ac, seed = client
    tenant_id = seed["t1"].id
    db_session.add_all(
        [
            m.Product(
                tenant_id=tenant_id, name="Sugar 1kg", sku="A-SUGAR-1KG",
                cost_price=10, selling_price=12, stock_qty=5, is_active=True,
            ),
            m.Product(
                tenant_id=tenant_id, name="Sugar cubes", sku="A-SUGAR-CUBE", barcode="SUGAR",
                cost_price=10, selling_price=12, stock_qty=5, is_active=True,
            ),
            m.Product(
                tenant_id=tenant_id, name="Baby Wipes (80 pack)", sku="A-WIPES",
                cost_price=18, selling_price=25, stock_qty=5, is_active=True,
            ),
        ]
    )
    await db_session.commit()
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    async def names(query: str) -> list[str]:
        r = await ac.get(f"/api/v1/pos/products/search?{query}", headers=headers)
        assert r.status_code == 200, r.text
        return [p["name"] for p in r.json()["data"]]

    # A word with no exact barcode/SKU match searches names.
    assert "Baby Wipes (80 pack)" in await names("q=baby")
    # A word that is an exact barcode still returns only that product (scanner first).
    assert await names("q=sugar") == ["Sugar cubes"]
    # The explicit barcode parameter stays exact-only.
    assert await names("barcode=baby") == []
