"""Stage 99 T1 — Quote-to-Order pipeline honesty."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_shell_and_quote_order_ui_t1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Quotations" in shell
    assert "/sales?tab=quotations" in shell
    assert "Customer Groups" in shell
    assert "/sales?tab=groups" in shell
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "quoteStatusFilter" in sales
    assert "Confirm required to reserve" in sales or "Confirm is required to reserve" in sales
    assert "setOrderStatus" in sales
    assert "order_status" in sales


def test_quotation_order_status_in_api():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "Confirm required to reserve stock" in api
    assert "async def list_quotations" in api
    assert "async def list_sales_orders" in api


@pytest.mark.asyncio
async def test_quotations_and_orders_status_filter_api(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad_q = await ac.get("/api/v1/sales/quotations?status=bogus", headers=headers)
    assert bad_q.status_code == 400
    bad_o = await ac.get("/api/v1/sales/orders?status=bogus", headers=headers)
    assert bad_o.status_code == 400

    quotes = await ac.get("/api/v1/sales/quotations?status=draft", headers=headers)
    assert quotes.status_code == 200, quotes.text
    for row in quotes.json().get("data") or []:
        assert row["status"] == "draft"

    orders = await ac.get("/api/v1/sales/orders?status=confirmed", headers=headers)
    assert orders.status_code == 200, orders.text
    for row in orders.json().get("data") or []:
        assert row["status"] == "confirmed"
