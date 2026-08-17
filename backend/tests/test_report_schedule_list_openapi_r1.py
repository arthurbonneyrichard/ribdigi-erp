"""GET /reports/schedules enabled+frequency Query OpenAPI + Email schedules filters (BR-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ScheduleFrequencyValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_schedule_frequency_literal_schema():
    adapter = TypeAdapter(ScheduleFrequencyValue)
    assert adapter.validate_python("daily") == "daily"
    assert adapter.validate_python("  Weekly ") == "weekly"
    assert adapter.validate_python("DAILY") == "daily"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("monthly")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_schedule_list_filters_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "scheduleManageFilter" in page
    assert "scheduleFrequencyFilter" in page
    assert "managedSchedules" in page
    assert 'aria-label="Report schedule enabled filter"' in page
    assert 'aria-label="Report schedule frequency filter"' in page
    assert 'value="enabled"' in page
    assert 'value="disabled"' in page
    assert 'value="daily"' in page
    assert 'value="weekly"' in page
    assert "No schedules for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report schedule list Query OpenAPI" in agents
    assert "scheduleManageFilter" in agents
    assert "scheduleFrequencyFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "scheduleManageFilter" in docs
    assert "scheduleFrequencyFilter" in docs
    assert "GET /reports/schedules" in docs


@pytest.mark.asyncio
async def test_schedule_list_query_blank_invalid_and_filters(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/schedules?frequency=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad_freq = await ac.get("/api/v1/reports/schedules?frequency=monthly", headers=headers)
    assert bad_freq.status_code == 422, bad_freq.text

    bad_enabled = await ac.get("/api/v1/reports/schedules?enabled=maybe", headers=headers)
    assert bad_enabled.status_code == 422, bad_enabled.text

    marker = "scheduleManageFilter hello-world"
    daily_on = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={
            "name": f"{marker} daily on",
            "report_type": "summary",
            "format": "csv",
            "frequency": "daily",
            "hour_utc": 7,
            "recipients": ["ops-daily@example.com"],
            "enabled": True,
        },
    )
    assert daily_on.status_code in {200, 201}, daily_on.text
    daily_id = daily_on.json()["data"]["id"]

    weekly_off = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={
            "name": f"{marker} weekly off",
            "report_type": "summary",
            "format": "xlsx",
            "frequency": "weekly",
            "weekday": 1,
            "hour_utc": 8,
            "recipients": ["ops-weekly@example.com"],
            "enabled": False,
        },
    )
    assert weekly_off.status_code in {200, 201}, weekly_off.text
    weekly_id = weekly_off.json()["data"]["id"]

    enabled_rows = await ac.get("/api/v1/reports/schedules?enabled=true", headers=headers)
    assert enabled_rows.status_code == 200, enabled_rows.text
    edata = enabled_rows.json()["data"] or []
    assert edata
    assert all(r.get("enabled") is True for r in edata)
    assert any(r.get("id") == daily_id for r in edata)
    assert all(r.get("id") != weekly_id for r in edata)

    disabled_rows = await ac.get("/api/v1/reports/schedules?enabled=false", headers=headers)
    assert disabled_rows.status_code == 200, disabled_rows.text
    ddata = disabled_rows.json()["data"] or []
    assert ddata
    assert all(r.get("enabled") is False for r in ddata)
    assert any(r.get("id") == weekly_id for r in ddata)

    daily_rows = await ac.get("/api/v1/reports/schedules?frequency=daily", headers=headers)
    assert daily_rows.status_code == 200, daily_rows.text
    assert all(r.get("frequency") == "daily" for r in (daily_rows.json()["data"] or []))
    assert any(r.get("id") == daily_id for r in (daily_rows.json()["data"] or []))

    weekly_rows = await ac.get("/api/v1/reports/schedules?frequency=weekly", headers=headers)
    assert weekly_rows.status_code == 200, weekly_rows.text
    assert all(r.get("frequency") == "weekly" for r in (weekly_rows.json()["data"] or []))
    assert any(r.get("id") == weekly_id for r in (weekly_rows.json()["data"] or []))

    both = await ac.get(
        "/api/v1/reports/schedules?enabled=false&frequency=weekly",
        headers=headers,
    )
    assert both.status_code == 200, both.text
    bdata = both.json()["data"] or []
    assert bdata
    assert all(r.get("enabled") is False and r.get("frequency") == "weekly" for r in bdata)
    assert any(r.get("id") == weekly_id for r in bdata)
