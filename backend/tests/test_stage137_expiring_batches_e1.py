"""Stage 137 E1 — expiring batches CSV export."""

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
async def test_expiring_batches_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    product = m.Product(
        tenant_id=seed["t1"].id,
        name="Stage137 Batch Product",
        sku="SKU-137-BAT",
        stock_qty=10,
        selling_price=1,
        cost_price=1,
        tracks_batches=True,
    )
    db_session.add(product)
    await db_session.flush()

    soon = m.ProductBatch(
        tenant_id=seed["t1"].id,
        product_id=product.id,
        batch_number="BAT-137-SOON",
        quantity=5,
        expiry_date=datetime.utcnow() + timedelta(days=20),
    )
    later = m.ProductBatch(
        tenant_id=seed["t1"].id,
        product_id=product.id,
        batch_number="BAT-137-LATER",
        quantity=5,
        expiry_date=datetime.utcnow() + timedelta(days=80),
    )
    db_session.add_all([soon, later])
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/inventory/batches/expiring/export?days=30", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "batch_number" in header and "expiry_date" in header
    assert "BAT-137-SOON" in exported.text
    assert "BAT-137-LATER" not in exported.text


def test_expiring_batches_ui_e1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 137" in page
    assert "/inventory/batches/expiring/export" in page
    assert "Export expiring batches CSV" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "expiry_days=30" in shell
    assert "Expiring in 30 Days" in shell
    assert "Expiring in 90 Days" in shell
