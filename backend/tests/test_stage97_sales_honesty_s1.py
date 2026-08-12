"""Stage 97 S1 — Sales surface honesty (invoice status + quotation convert copy)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_page_invoice_status_and_quotation_honesty_ui():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "invoiceStatusFilter" in sales
    assert "unpaid" in sales
    assert "Post is required before AR" in sales or "Post required before AR" in sales
    assert "Filter invoices by status" in sales


def test_list_sales_invoices_status_param_in_api():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "async def list_sales_invoices" in api
    assert 'key == "unpaid"' in api or "unpaid" in api
    assert "posted" in api and "sent" in api
    assert "Post required before AR" in api


@pytest.mark.asyncio
async def test_sales_invoice_status_filter_api(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad = await ac.get("/api/v1/sales/invoices?status=bogus", headers=headers)
    assert bad.status_code == 400

    all_inv = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert all_inv.status_code == 200, all_inv.text
    unpaid = await ac.get("/api/v1/sales/invoices?status=unpaid", headers=headers)
    assert unpaid.status_code == 200, unpaid.text
    for row in unpaid.json().get("data") or []:
        assert row["status"] in {"posted", "sent"}

    paid = await ac.get("/api/v1/sales/invoices?status=paid", headers=headers)
    assert paid.status_code == 200
    for row in paid.json().get("data") or []:
        assert row["status"] == "paid"
