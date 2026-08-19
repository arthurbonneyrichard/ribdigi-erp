"""Stage 127 S1 — report-schedule enabled filter + CSV."""

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
async def test_report_schedules_enabled_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={
            "name": "Stage127 Disabled Sched",
            "report_type": "summary",
            "format": "csv",
            "frequency": "daily",
            "hour_utc": 7,
            "recipients": ["ops@example.com"],
            "enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/reports/schedules/{sid}",
        headers=headers,
        json={"enabled": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["enabled"] is False

    disabled = await ac.get("/api/v1/reports/schedules?enabled=false", headers=headers)
    assert disabled.status_code == 200, disabled.text
    rows = disabled.json()["data"]
    assert any(r["id"] == sid for r in rows)
    assert all(r.get("enabled") is False for r in rows)

    enabled = await ac.get("/api/v1/reports/schedules?enabled=true", headers=headers)
    assert enabled.status_code == 200, enabled.text
    assert not any(r["id"] == sid for r in enabled.json()["data"])

    exported = await ac.get(
        "/api/v1/reports/schedules/export?enabled=false", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "report_type" in header and "enabled" in header
    assert "Stage127 Disabled Sched" in exported.text


def test_reports_schedule_export_ui_s1():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "Stage 127" in page
    assert "/reports/schedules/export" in page
    assert "Export schedules CSV" in page
    svc = (ROOT / "backend/app/api_fx_schedule_export.py").read_text(encoding="utf-8")
    assert "export_report_schedules_csv" in svc
