"""Stage 134 R1 — purchase request register CSV export."""

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
async def test_purchase_requests_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    supplier = m.Party(
        tenant_id=seed["t1"].id, name="Stage134 Supplier", kind="supplier", credit_limit=0
    )
    db_session.add(supplier)
    await db_session.flush()

    db_session.add_all(
        [
            m.PurchaseRequest(
                tenant_id=seed["t1"].id,
                request_number="PR-134-DRAFT",
                supplier_id=supplier.id,
                status="draft",
                estimated_total=10,
            ),
            m.PurchaseRequest(
                tenant_id=seed["t1"].id,
                request_number="PR-134-PEND",
                supplier_id=supplier.id,
                status="pending",
                estimated_total=20,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/purchasing/requests/export?status=draft", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "request_number" in header and "status" in header
    assert "items" not in header
    assert "PR-134-DRAFT" in exported.text
    assert "PR-134-PEND" not in exported.text


def test_purchase_requests_export_ui_r1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 134" in page
    assert "downloadPurchasingPipelineExport" in page
    assert "Export requests CSV" in page
