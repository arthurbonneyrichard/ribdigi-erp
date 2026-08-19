"""Stage 128 N1 — document numbering & print template settings CSV."""

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
async def test_document_settings_export(client):
    ac, seed = client
    headers = await _super(ac, seed)

    exported = await ac.get("/api/v1/tenants/me/document-settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    lines = exported.text.splitlines()
    header = lines[0]
    assert "section" in header and "key" in header and "prefix" in header
    assert "preview" in header
    body = "\n".join(lines[1:])
    assert "numbering" in body
    assert "sales_invoice" in body
    assert "print_template" in body
    assert "invoice_print_template" in body
    assert "receipt_print_template" in body


def test_company_document_settings_export_n1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 128" in page
    assert "/tenants/me/document-settings/export" in page
    assert "Export document settings CSV" in page
