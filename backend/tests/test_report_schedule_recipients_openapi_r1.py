"""ReportScheduleCreate / Update.recipients OpenAPI honesty (BR-14)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ReportScheduleCreate, ReportScheduleUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE = {
    "name": "Daily summary",
    "report_type": "summary",
    "format": "csv",
    "frequency": "daily",
}


def test_report_schedule_recipients_schema():
    ok = ReportScheduleCreate.model_validate(
        {**_BASE, "recipients": "  ops@example.com ; finance@example.com "}
    )
    assert ok.recipients == ["ops@example.com", "finance@example.com"]
    listed = ReportScheduleCreate.model_validate(
        {**_BASE, "recipients": ["ops@example.com"]}
    )
    assert listed.recipients == ["ops@example.com"]
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(_BASE)
    for bad in ("", " ", "bad", "almost@", "ops@example.com, bad", ["ops@example.com", "bad"], []):
        with pytest.raises(ValidationError):
            ReportScheduleCreate.model_validate({**_BASE, "recipients": bad})

    patch_omit = ReportScheduleUpdate.model_validate({})
    assert patch_omit.recipients is None
    patch_ok = ReportScheduleUpdate.model_validate({"recipients": "a@example.com"})
    assert patch_ok.recipients == ["a@example.com"]
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"recipients": ""})
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"recipients": "not-an-email"})


def test_report_schedule_recipients_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report schedule recipients"' in page
    assert 'aria-label="Create report schedule"' in page
    assert "schedForm.recipients.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report schedule recipients OpenAPI" in agents
    assert "ReportScheduleRecipientsValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Report schedule recipients" in docs
    assert "ReportScheduleRecipientsValue" in docs


@pytest.mark.asyncio
async def test_report_schedule_recipients_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    name = f"tip118-{uuid4().hex[:8]}"

    for bad in ("", "bad", "ops@example.com, bad"):
        resp = await ac.post(
            "/api/v1/reports/schedules",
            headers=headers,
            json={**_BASE, "name": name, "recipients": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={
            **_BASE,
            "name": name,
            "recipients": "ops@example.com, finance@example.com",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["recipients"] == ["ops@example.com", "finance@example.com"]
    schedule_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/reports/schedules/{schedule_id}",
        headers=headers,
        json={"recipients": "not-an-email"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/reports/schedules/{schedule_id}",
        headers=headers,
        json={"recipients": ["ops@example.com"]},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["recipients"] == ["ops@example.com"]
