"""Stage 142 S1 — POS sales register list + CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_pos_sales_list_and_export_csv(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.selling_price = 25
    product.stock_qty = 50
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "payments": [{"payment_method": "cash", "amount": 25}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    reference = sale.json()["data"].get("reference") or ""

    listed = await ac.get("/api/v1/pos/sales", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert any(r.get("id") == sale_id for r in rows)

    exported = await ac.get("/api/v1/pos/sales/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "reference" in header and "total" in header and "session_id" in header
    assert sale_id in text
    if reference:
        assert reference in text
    assert "25" in text

    filtered = await ac.get(
        f"/api/v1/pos/sales/export?session_id={session_id}", headers=headers
    )
    assert filtered.status_code == 200, filtered.text
    assert sale_id in filtered.text


def test_pos_sales_export_ui_s1():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "Stage 142" in page
    assert "/pos/sales/export" in page
    assert "Export sales CSV" in page
