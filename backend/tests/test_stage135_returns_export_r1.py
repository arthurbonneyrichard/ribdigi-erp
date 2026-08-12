"""Stage 135 R1 — purchase return register CSV export."""

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
async def test_purchase_returns_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    supplier = m.Party(
        tenant_id=seed["t1"].id, name="Stage135 Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    po = m.PurchaseOrder(
        tenant_id=seed["t1"].id,
        po_number="PO-135-RET",
        supplier_id=supplier.id,
        status="received",
    )
    db_session.add(po)
    await db_session.flush()

    grn = m.GoodsReceipt(
        tenant_id=seed["t1"].id,
        grn_number="GRN-135-RET",
        purchase_order_id=po.id,
        supplier_id=supplier.id,
        status="posted",
    )
    db_session.add(grn)
    await db_session.flush()

    db_session.add_all(
        [
            m.PurchaseReturn(
                tenant_id=seed["t1"].id,
                return_number="PRTN-135-DRAFT",
                supplier_id=supplier.id,
                purchase_order_id=po.id,
                goods_receipt_id=grn.id,
                status="draft",
                reason="damaged",
                total_amount=10,
            ),
            m.PurchaseReturn(
                tenant_id=seed["t1"].id,
                return_number="PRTN-135-POSTED",
                supplier_id=supplier.id,
                purchase_order_id=po.id,
                goods_receipt_id=grn.id,
                status="posted",
                reason="damaged",
                debit_note_number="DN-135",
                total_amount=20,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/purchasing/returns/export?status=draft", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "return_number" in header and "status" in header
    assert "items" not in header
    assert "PRTN-135-DRAFT" in exported.text
    assert "PRTN-135-POSTED" not in exported.text


def test_purchase_returns_export_ui_r1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 135" in page
    assert "downloadPurchasingPipelineExport" in page
    assert "Export returns CSV" in page
