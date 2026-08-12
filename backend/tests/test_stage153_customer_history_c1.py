"""Stage 153 C1 — customer history CSV export."""

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
async def test_customer_history_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)
    customer_id = seed["party1"].id
    exported = await ac.get(
        f"/api/v1/customers/{customer_id}/history/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "party_kind" in header and "row_type" in header and "record_id" in header
    assert "customer" in text


def test_customer_history_export_ui_c1():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 153" in page
    assert "/history/export" in page
    assert "Export history CSV" in page
