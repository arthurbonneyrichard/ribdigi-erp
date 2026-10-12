"""FMCG module R2 — schemes, routes, delivery, near-expiry, preview."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.packages import PACKAGEABLE_MODULES
from tests.conftest import auth_headers, set_tenant_industry

ROOT = Path(__file__).resolve().parents[2]


def test_fmcg_module_registered():
    assert "fmcg" in PACKAGEABLE_MODULES
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "['FMCG overview', '/fmcg', 'fmcg']" in nav
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "FMCG_NAV_ITEMS" not in shell
    page = (ROOT / "frontend/app/(dashboard)/fmcg/page.tsx").read_text(encoding="utf-8")
    assert "/fmcg/schemes" in page
    assert "/fmcg/routes" in page


def _fmcg_disabled(resp) -> None:
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


@pytest.mark.asyncio
async def test_fmcg_scheme_route_stop_lifecycle(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:6]
    product_name = f"Outlet Item {suffix}"
    product = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": product_name, "sku": f"SKU{suffix}", "selling_price": 10, "cost_price": 4},
    )
    assert product.status_code == 200, product.text

    _fmcg_disabled(
        await ac.post(
            "/api/v1/fmcg/schemes",
            headers=admin,
            json={"code": f"SC{suffix}", "name": f"Scheme {suffix}", "scheme_type": "percent", "value": 10},
        )
    )
    _fmcg_disabled(
        await ac.post(
            "/api/v1/fmcg/schemes/preview",
            headers=admin,
            json={"line_qty": 10, "line_amount": 100},
        )
    )
    _fmcg_disabled(
        await ac.post(
            "/api/v1/fmcg/routes",
            headers=admin,
            json={"code": f"RT{suffix}", "name": f"Route {suffix}", "driver_name": "Driver A", "vehicle": "Van-1"},
        )
    )
    _fmcg_disabled(await ac.get("/api/v1/fmcg/routes/performance", headers=admin))
    _fmcg_disabled(await ac.get("/api/v1/fmcg/expiring?days=30", headers=admin))
    _fmcg_disabled(await ac.get("/api/v1/fmcg/summary", headers=admin))

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    beta_schemes = await ac.get("/api/v1/fmcg/schemes", headers=beta)
    _fmcg_disabled(beta_schemes)
    assert product_name not in beta_schemes.text
    beta_products = await ac.get("/api/v1/products", headers=beta)
    assert product_name not in beta_products.text
    if beta_products.status_code == 200:
        assert all(row.get("name") != product_name for row in beta_products.json()["data"])


@pytest.mark.asyncio
async def test_fmcg_duplicate_scheme_code_blocked(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:6]
    payload = {
        "code": f"DUP{suffix}",
        "name": f"Dup {suffix}",
        "scheme_type": "fixed",
        "value": 5,
    }
    first = await ac.post("/api/v1/fmcg/schemes", headers=admin, json=payload)
    _fmcg_disabled(first)
    clash = await ac.post("/api/v1/fmcg/schemes", headers=admin, json=payload)
    _fmcg_disabled(clash)
    assert suffix.upper() not in first.text
    assert suffix.upper() not in clash.text
