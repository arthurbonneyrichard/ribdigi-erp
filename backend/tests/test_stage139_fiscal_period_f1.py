"""Stage 139 F1 — fiscal period CSV export."""

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
async def test_fiscal_period_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    status = await ac.get("/api/v1/accounting/fiscal-period", headers=headers)
    assert status.status_code == 200, status.text
    body = status.json()["data"]

    exported = await ac.get("/api/v1/accounting/fiscal-period/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "fiscal_year_start" in header
    assert "open_period_start" in header
    assert "current_period_closed" in header
    assert "closed_period_starts" in header
    assert body["open_period_start"] in text
    assert body["fiscal_year_start"] in text


def test_fiscal_period_export_ui_f1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 139" in page
    assert "/accounting/fiscal-period/export" in page
    assert "Export fiscal period CSV" in page
