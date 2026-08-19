"""Stage 142 Z1 — POS session Z-report CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_pos_session_z_report_export_csv(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.selling_price = 40
    product.stock_qty = 50
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 120},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    session_number = opened.json()["data"].get("session_number") or ""

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "items": [{"product_id": product.id, "quantity": 1}],
            "payments": [{"payment_method": "card", "amount": 40}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]

    exported = await ac.get(
        f"/api/v1/pos/sessions/{session_id}/report/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "session_id" in header and "sale_id" in header
    assert "session" in text
    assert "sale" in text
    assert session_id in text
    assert sale_id in text
    if session_number:
        assert session_number in text
    assert "40" in text


def test_z_report_export_ui_z1():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "Stage 142" in page
    assert "/report/export" in page
    assert "Export Z-report CSV" in page
