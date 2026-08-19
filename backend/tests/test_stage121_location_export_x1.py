"""Stage 121 X1 — stores / warehouses / tax rates CSV export."""

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
async def test_stores_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "EXP121S", "name": "Export Store 121"},
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/stores/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    assert "code" in text.splitlines()[0]
    assert "EXP121S" in text or "Export Store 121" in text


@pytest.mark.asyncio
async def test_warehouses_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"code": "EXP121W", "name": "Export WH 121", "warehouse_type": "main"},
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/warehouses/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    assert "warehouse_type" in text.splitlines()[0]
    assert "EXP121W" in text or "Export WH 121" in text


@pytest.mark.asyncio
async def test_tax_rates_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": "Stage121 Export VAT", "rate": 12.5, "tax_type": "vat"},
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/tax/rates/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    assert "pricing_mode" in text.splitlines()[0]
    assert "Stage121 Export VAT" in text


def test_location_export_ui_and_service_x1():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 121" in stores
    assert "/stores/export" in stores
    assert "Export stores CSV" in stores
    assert "/warehouses/export" in stores
    assert "Export warehouses CSV" in stores
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert "Stage 121" in tax
    assert "/tax/rates/export" in tax
    assert "Export tax rates CSV" in tax
    svc = (ROOT / "backend/app/location_export.py").read_text(encoding="utf-8")
    assert "export_stores_csv" in svc
    assert "export_warehouses_csv" in svc
    assert "export_tax_rates_csv" in svc
