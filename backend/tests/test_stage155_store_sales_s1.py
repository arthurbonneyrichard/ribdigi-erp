"""Stage 155 S1 — store sales CSV export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app import models as m
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_store_sales_export_csv(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    store = await create_store(
        db_session, tenant_id=tenant_id, code="SAL155", name="Stage 155 Sales Store"
    )
    await db_session.flush()
    now = datetime.utcnow()
    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-155-1",
        customer_id=seed["party1"].id,
        store_id=store.id,
        status="posted",
        subtotal=100,
        tax_amount=10,
        total_amount=110,
        posted_at=now,
    )
    session = m.PosSession(
        tenant_id=tenant_id,
        store_id=store.id,
        user_id=seed["mgr1"].id,
        session_number="SESS-155-1",
        status="open",
        opening_cash=0,
    )
    db_session.add_all([inv, session])
    await db_session.flush()
    pos = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-155-1",
        session_id=session.id,
        subtotal=20,
        tax=2,
        total=22,
        status="completed",
    )
    db_session.add(pos)
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/stores/{store.id}/sales/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "revenue" in header and "source" in header
    assert "summary" in text
    assert "INV-155-1" in text
    assert "POS-155-1" in text


def test_store_sales_export_ui_s1():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 155" in page
    assert "/sales/export" in page
    assert "Export sales CSV" in page
