"""Stage 134 G1 — GRN register CSV export."""

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
async def test_grn_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    supplier = m.Party(
        tenant_id=seed["t1"].id, name="Stage134 GRN Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    po = m.PurchaseOrder(
        tenant_id=seed["t1"].id,
        po_number="PO-134-GRN",
        supplier_id=supplier.id,
        status="sent",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
    )
    db_session.add(po)
    await db_session.flush()

    db_session.add_all(
        [
            m.GoodsReceipt(
                tenant_id=seed["t1"].id,
                grn_number="GRN-134-DRAFT",
                purchase_order_id=po.id,
                supplier_id=supplier.id,
                status="draft",
                notes="Stage134 draft",
            ),
            m.GoodsReceipt(
                tenant_id=seed["t1"].id,
                grn_number="GRN-134-POSTED",
                purchase_order_id=po.id,
                supplier_id=supplier.id,
                status="posted",
                notes="Stage134 posted",
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/purchasing/grn/export?status=posted", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "grn_number" in header and "status" in header
    assert "items" not in header
    assert "GRN-134-POSTED" in exported.text
    assert "GRN-134-DRAFT" not in exported.text


def test_grn_export_ui_g1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 134" in page
    assert "downloadPurchasingPipelineExport" in page
    assert "Export GRNs CSV" in page
