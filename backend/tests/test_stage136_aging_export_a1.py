"""Stage 136 A1 — credit aging document CSV export."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_aging_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    customer = m.Party(
        tenant_id=seed["t1"].id, name="Stage136 Aging Cust", kind="customer", credit_limit=0
    )
    db_session.add(customer)
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-136-AGE",
        customer_id=customer.id,
        status="posted",
        total_amount=200,
        paid_amount=0,
        due_date=datetime.utcnow() - timedelta(days=5),
        posted_at=datetime.utcnow() - timedelta(days=10),
    )
    db_session.add(inv)
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/credit/aging/export?kind=receivable", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "document_number" in header and "bucket" in header and "kind" in header
    assert "INV-136-AGE" in exported.text
    assert "receivable" in exported.text

    bad = await ac.get("/api/v1/credit/aging/export?kind=nope", headers=headers)
    assert bad.status_code == 400


def test_aging_export_ui_a1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 136" in page
    assert "/credit/aging/export" in page
    assert "Export aging CSV" in page
