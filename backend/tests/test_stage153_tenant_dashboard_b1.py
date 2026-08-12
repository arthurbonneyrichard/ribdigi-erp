"""Stage 153 B1 — tenant dashboard aggregates CSV export."""

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
async def test_tenant_dashboard_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)
    exported = await ac.get("/api/v1/dashboard/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "section" in header
    assert "kpi" in text
    assert "total_sales" in text or "products" in text or "customers" in text


def test_tenant_dashboard_export_ui_b1():
    page = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Stage 153" in page
    assert "/dashboard/export" in page
    assert "Export aggregates CSV" in page
