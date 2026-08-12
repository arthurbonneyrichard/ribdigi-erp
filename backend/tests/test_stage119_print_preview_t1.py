"""Stage 119 T1 — print template sample preview."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_print_templates_sample_preview(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    inv = await ac.get(
        "/api/v1/tenants/me/print-templates/preview?kind=invoice&format=html&template=a4",
        headers=headers,
    )
    assert inv.status_code == 200, inv.text
    assert "text/html" in inv.headers.get("content-type", "")
    assert "INV-SAMPLE-0001" in inv.text
    assert "Sample Customer" in inv.text or "Sample Widget" in inv.text

    receipt = await ac.get(
        "/api/v1/tenants/me/print-templates/preview?kind=receipt&format=text&template=thermal_80",
        headers=headers,
    )
    assert receipt.status_code == 200, receipt.text
    assert "POS-SAMPLE-0001" in receipt.text
    assert "Sample Item" in receipt.text

    bad = await ac.get(
        "/api/v1/tenants/me/print-templates/preview?kind=bogus",
        headers=headers,
    )
    assert bad.status_code == 400


def test_company_page_print_preview_t1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 119" in page
    assert "/tenants/me/print-templates/preview" in page
    assert "Preview sample invoice" in page
    assert "Preview sample receipt" in page
    svc = (ROOT / "backend/app/print_preview.py").read_text(encoding="utf-8")
    assert "render_sample_invoice_preview" in svc
    assert "render_sample_receipt_preview" in svc
