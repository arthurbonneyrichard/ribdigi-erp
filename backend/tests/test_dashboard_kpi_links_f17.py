"""Stage 1 F17 — dashboard KPI click-through links (BR-4.1)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_dashboard_kpi_links_point_to_modules(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    links = r.json()["data"]["kpi_links"]
    required = {
        "total_sales": "/sales?tab=invoices",
        "total_purchases": "/purchasing?tab=invoices",
        "total_expenses": "/expenses",
        "customers": "/sales?tab=customers",
        "suppliers": "/purchasing?tab=suppliers",
        "products": "/inventory?tab=products",
        "low_stock": "/inventory?tab=lowstock",
        "out_of_stock": "/inventory?tab=lowstock",
        "expiring_batches": "/inventory?tab=expiry",
        "daily_revenue": "/reports?tab=sales",
        "monthly_revenue": "/reports?tab=sales",
    }
    for key, path in required.items():
        assert links.get(key) == path, key
