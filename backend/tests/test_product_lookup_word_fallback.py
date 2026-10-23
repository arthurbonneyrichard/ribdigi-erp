"""Inventory product lookup: a plain word that looks like a barcode still finds products by name."""

from __future__ import annotations

import pytest

from app import inventory as inventory_svc
from app import models as m


@pytest.mark.asyncio
async def test_lookup_word_falls_back_to_name(db_session, seeded):
    tenant_id = seeded["t1"].id
    db_session.add(m.Product(tenant_id=tenant_id, name="Rice 5kg", sku="SKU-LOOKUP-RICE", category="Groceries"))
    await db_session.flush()

    found = await inventory_svc.lookup_products(db_session, tenant_id, q="rice")
    assert found["barcode"] is None
    assert any(item["name"] == "Rice 5kg" for item in found["items"])

    exact = await inventory_svc.lookup_products(db_session, tenant_id, q="SKU-LOOKUP-RICE")
    assert exact["barcode"] == "SKU-LOOKUP-RICE"
    assert [item["name"] for item in exact["items"]] == ["Rice 5kg"]
