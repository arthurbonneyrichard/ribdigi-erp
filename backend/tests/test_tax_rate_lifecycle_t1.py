"""Stage 14 T1: tax rate edit/deactivate + report period helpers."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from app import reports as reports_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_quarter_and_year_bounds_helpers():
    start, end = reports_svc.quarter_bounds(2026, 2)
    assert start == datetime(2026, 4, 1)
    assert end == datetime(2026, 6, 30, 23, 59, 59, 999999)

    y_start, y_end = reports_svc.year_bounds(2026)
    assert y_start == datetime(2026, 1, 1)
    assert y_end == datetime(2026, 12, 31, 23, 59, 59, 999999)

    fd, td, meta = reports_svc.resolve_report_period(
        period="monthly", year=2026, month=3, ref=datetime(2026, 8, 1)
    )
    assert meta["period"] == "monthly"
    assert meta["year"] == 2026 and meta["month"] == 3
    assert fd == datetime(2026, 3, 1)
    assert td.date().isoformat() == "2026-03-31"

    fd, td, meta = reports_svc.resolve_report_period(
        period="quarterly", year=2026, quarter=1, ref=datetime(2026, 8, 1)
    )
    assert meta["period"] == "quarterly" and meta["quarter"] == 1
    assert fd == datetime(2026, 1, 1)
    assert td.date().isoformat() == "2026-03-31"

    fd, td, meta = reports_svc.resolve_report_period(
        period="annually", year=2025, ref=datetime(2026, 8, 1)
    )
    assert meta["period"] == "annually" and meta["year"] == 2025
    assert fd == datetime(2025, 1, 1)
    assert td.date().isoformat() == "2025-12-31"


@pytest.mark.asyncio
async def test_tax_rate_patch_deactivate_and_period_report(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "Standard VAT T1",
            "rate": 15,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": True,
            "is_active": True,
        },
    )
    assert created.status_code == 200, created.text
    rate_id = created.json()["data"]["id"]
    assert created.json()["data"]["is_default"] is True

    second = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "Reduced VAT T1",
            "rate": 5,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": False,
            "is_active": True,
        },
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/tax/rates/{second_id}",
        headers=headers,
        json={"name": "Reduced VAT 5%", "rate": 5.5, "pricing_mode": "inclusive"},
    )
    assert patched.status_code == 200, patched.text
    pdata = patched.json()["data"]
    assert pdata["name"] == "Reduced VAT 5%"
    assert float(pdata["rate"]) == pytest.approx(5.5)
    assert pdata["pricing_mode"] == "inclusive"

    deactivated = await ac.patch(
        f"/api/v1/tax/rates/{rate_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    ddata = deactivated.json()["data"]
    assert ddata["is_active"] is False
    assert ddata["is_default"] is False  # cleared on deactivate

    active_only = await ac.get(
        "/api/v1/tax/rates",
        headers=headers,
        params={"active_only": True},
    )
    assert active_only.status_code == 200, active_only.text
    active_ids = {r["id"] for r in active_only.json()["data"]}
    assert second_id in active_ids
    assert rate_id not in active_ids

    # Reactivate + set default via patch
    revived = await ac.patch(
        f"/api/v1/tax/rates/{rate_id}",
        headers=headers,
        json={"is_active": True, "is_default": True, "rate": 15},
    )
    assert revived.status_code == 200, revived.text
    assert revived.json()["data"]["is_default"] is True
    assert revived.json()["data"]["is_active"] is True

    other = await ac.get(f"/api/v1/tax/rates/{second_id}", headers=headers)
    assert other.status_code == 200
    assert other.json()["data"]["is_default"] is False

    # Cross-tenant rate id → 404
    foreign_rate = m.TaxRate(
        tenant_id=seed["t2"].id,
        name="Beta VAT",
        rate=10,
        tax_type="vat",
        pricing_mode="exclusive",
        is_active=True,
        is_default=True,
    )
    db_session.add(foreign_rate)
    await db_session.commit()
    foreign = await ac.patch(
        f"/api/v1/tax/rates/{foreign_rate.id}",
        headers=headers,
        json={"name": "Hijack"},
    )
    assert foreign.status_code == 404, foreign.text

    monthly = await ac.get(
        "/api/v1/reports/tax",
        headers=headers,
        params={"period": "monthly", "year": 2026, "month": 6},
    )
    assert monthly.status_code == 200, monthly.text
    mdata = monthly.json()["data"]
    assert mdata["period"] == "monthly"
    assert mdata["period_year"] == 2026
    assert mdata["period_month"] == 6
    assert str(mdata["from_date"]).startswith("2026-06-01")
    assert "2026-06-30" in str(mdata["to_date"])

    quarterly = await ac.get(
        "/api/v1/reports/tax/filing",
        headers=headers,
        params={"period": "quarterly", "year": 2026, "quarter": 2},
    )
    assert quarterly.status_code == 200, quarterly.text
    qdata = quarterly.json()["data"]
    assert qdata["period"] == "quarterly"
    assert qdata["period_quarter"] == 2

    annual_resp = await ac.get(
        "/api/v1/reports/tax",
        headers=headers,
        params={"period": "annually", "year": 2026},
    )
    assert annual_resp.status_code == 200, annual_resp.text
    assert annual_resp.json()["data"]["period"] == "annually"
    assert annual_resp.json()["data"]["period_year"] == 2026

    bad = await ac.get(
        "/api/v1/reports/tax",
        headers=headers,
        params={"period": "weekly"},
    )
    assert bad.status_code == 400, bad.text
