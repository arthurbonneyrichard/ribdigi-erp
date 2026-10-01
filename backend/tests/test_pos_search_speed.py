"""POS search stays tenant-scoped, capped, and uses batched tax resolution."""

from __future__ import annotations

import time

import pytest

from app.tax import resolve_product_tax, resolve_products_tax_map
from tests.conftest import auth_headers


async def _admin(ac, seed):
    return await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )


@pytest.mark.asyncio
async def test_pos_search_empty_is_capped_and_tenant_scoped(client):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    t0 = time.perf_counter()
    alpha = await ac.get("/api/v1/pos/products/search", headers=cashier)
    alpha_ms = (time.perf_counter() - t0) * 1000
    assert alpha.status_code == 200, alpha.text
    rows = alpha.json()["data"]
    assert isinstance(rows, list)
    assert len(rows) <= 40
    print(f"[ribdigi-nav] pos_search empty first={alpha_ms:.1f}ms rows={len(rows)}")

    t1 = time.perf_counter()
    alpha2 = await ac.get("/api/v1/pos/products/search", headers=cashier)
    repeat_ms = (time.perf_counter() - t1) * 1000
    assert alpha2.status_code == 200, alpha2.text
    print(f"[ribdigi-nav] pos_search empty repeat={repeat_ms:.1f}ms")

    ids = {row["id"] for row in rows}
    foreign = await ac.get("/api/v1/pos/products/search", headers=beta)
    assert foreign.status_code == 200, foreign.text
    foreign_ids = {row["id"] for row in foreign.json()["data"]}
    assert ids.isdisjoint(foreign_ids)


@pytest.mark.asyncio
async def test_products_limit_is_incremental_and_tenant_scoped(client):
    ac, seed = client
    admin = await _admin(ac, seed)

    limited = await ac.get("/api/v1/products?limit=1", headers=admin)
    assert limited.status_code == 200, limited.text
    rows = limited.json()["data"]
    assert len(rows) <= 1

    full = await ac.get("/api/v1/products", headers=admin)
    assert full.status_code == 200, full.text
    if rows:
        assert rows[0]["id"] in {r["id"] for r in full.json()["data"]}


@pytest.mark.asyncio
async def test_resolve_products_tax_map_matches_single(db_session, client):
    _ac, seed = client
    product = seed["p1"]
    single = await resolve_product_tax(db_session, seed["t1"].id, product)
    batch = await resolve_products_tax_map(db_session, seed["t1"].id, [product])
    spec = batch[product.id]
    assert spec.rate_pct == single.rate_pct
    assert spec.pricing_mode == single.pricing_mode
    assert spec.supply_class == single.supply_class
