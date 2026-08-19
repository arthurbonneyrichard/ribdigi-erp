"""Stage 127 F1 — FX rates CSV export."""

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
async def test_exchange_rates_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    upserted = await ac.put(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
        json={"currency_code": "USD", "rate_to_base": 12.5},
    )
    assert upserted.status_code == 200, upserted.text

    exported = await ac.get("/api/v1/credit/exchange-rates/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "currency_code" in header and "rate_to_base" in header
    assert "USD" in exported.text
    assert "12.5" in exported.text or "12.50" in exported.text


def test_credit_fx_export_ui_f1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 127" in page
    assert "/credit/exchange-rates/export" in page
    assert "Export FX rates CSV" in page
    svc = (ROOT / "backend/app/api_fx_schedule_export.py").read_text(encoding="utf-8")
    assert "export_exchange_rates_csv" in svc
