"""Stage 133 Q1 — sales quotation register CSV export."""

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
async def test_quotations_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    db_session.add_all(
        [
            m.SalesQuotation(
                tenant_id=seed["t1"].id,
                quotation_number="Q-133-DRAFT",
                customer_id=seed["party1"].id,
                status="draft",
                subtotal=10,
                tax_amount=0,
                total_amount=10,
            ),
            m.SalesQuotation(
                tenant_id=seed["t1"].id,
                quotation_number="Q-133-SENT",
                customer_id=seed["party1"].id,
                status="sent",
                subtotal=20,
                tax_amount=0,
                total_amount=20,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/sales/quotations/export?status=draft", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "quotation_number" in header and "status" in header
    assert "items" not in header
    assert "Q-133-DRAFT" in exported.text
    assert "Q-133-SENT" not in exported.text


def test_quotations_export_ui_q1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 133" in page
    assert "downloadPipelineExport" in page
    assert "Export quotations CSV" in page
    assert "/sales/${kind}/export" in page or "sales/${kind}/export" in page
