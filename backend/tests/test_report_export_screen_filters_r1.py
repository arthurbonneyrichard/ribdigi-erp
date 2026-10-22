"""Export and sales-by-store use the same filters the reports screen shows."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_export_status_and_reason_match_screen_filters(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get(
        "/api/v1/reports/export?report_type=inventory_transfers&format=csv&status=",
        headers=headers,
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.get(
        "/api/v1/reports/export?report_type=sales_returns&format=csv&reason=!!!",
        headers=headers,
    )
    assert garbage.status_code == 422, garbage.text

    transfers = await ac.get(
        "/api/v1/reports/export?report_type=inventory_transfers&format=csv&status=received",
        headers=headers,
    )
    assert transfers.status_code == 200, transfers.text
    assert "text/csv" in transfers.headers.get("content-type", "")

    returns = await ac.get(
        "/api/v1/reports/export?report_type=sales_returns&format=csv&status=posted&reason=damaged",
        headers=headers,
    )
    assert returns.status_code == 200, returns.text

    counts = await ac.get(
        "/api/v1/reports/export?report_type=inventory_stock_counts&format=csv&status=draft",
        headers=headers,
    )
    assert counts.status_code == 200, counts.text

    pending = await ac.get(
        "/api/v1/reports/export?report_type=purchases_pending_orders&format=csv&status=sent",
        headers=headers,
    )
    assert pending.status_code == 200, pending.text


@pytest.mark.asyncio
async def test_sales_by_store_and_department_store_id_query(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for path in ("/api/v1/reports/sales/by-store", "/api/v1/reports/sales/by-department"):
        blank = await ac.get(f"{path}?store_id=", headers=headers)
        assert blank.status_code == 422, (path, blank.text)
        bad = await ac.get(f"{path}?store_id=!!!", headers=headers)
        assert bad.status_code == 422, (path, bad.text)
        omitted = await ac.get(path, headers=headers)
        assert omitted.status_code == 200, (path, omitted.text)
        missing = await ac.get(f"{path}?store_id={uuid4()}", headers=headers)
        assert missing.status_code in (200, 400, 404), (path, missing.text)
        assert missing.status_code != 422
