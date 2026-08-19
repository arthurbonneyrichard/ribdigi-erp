"""Stage 133 O1 — sales order register CSV export."""

from __future__ import annotations

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
async def test_orders_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    db_session.add_all(
        [
            m.SalesOrder(
                tenant_id=seed["t1"].id,
                order_number="SO-133-DRAFT",
                customer_id=seed["party1"].id,
                status="draft",
                subtotal=10,
                tax_amount=0,
                total_amount=10,
            ),
            m.SalesOrder(
                tenant_id=seed["t1"].id,
                order_number="SO-133-CONF",
                customer_id=seed["party1"].id,
                status="confirmed",
                subtotal=30,
                tax_amount=0,
                total_amount=30,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/sales/orders/export?status=confirmed", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "order_number" in header and "status" in header
    assert "items" not in header
    assert "SO-133-CONF" in exported.text
    assert "SO-133-DRAFT" not in exported.text


def test_orders_export_ui_o1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 133" in page
    assert "downloadPipelineExport" in page
    assert "Export orders CSV" in page
