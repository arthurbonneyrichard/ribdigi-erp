"""ReportScheduleCreate / Update.name OpenAPI honesty (BR-14)."""

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
    "report_type": "summary",
    "format": "csv",
    "frequency": "daily",
    "recipients": ["ops@example.com"],
}


def test_report_schedule_name_schema():
    ok = ReportScheduleCreate.model_validate(
        {**_BASE, "name": "  Daily sales summary  "}
    )
    assert ok.name == "Daily sales summary"
    for bad in ("", " ", "!", "!!", "!!!", "http://evil", "@@", "X"):
        with pytest.raises(ValidationError):
            ReportScheduleCreate.model_validate({**_BASE, "name": bad})
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(_BASE)

    patch_omit = ReportScheduleUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = ReportScheduleUpdate.model_validate({"name": " Weekly P&L "})
    assert patch_ok.name == "Weekly P&L"
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        ReportScheduleUpdate.model_validate({"name": "  "})


def test_report_schedule_name_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report schedule name"' in page
    assert "schedForm.name.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Report schedule name OpenAPI" in agents
    assert "ReportScheduleNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Report schedule name" in docs
    assert "ReportScheduleNameValue" in docs


@pytest.mark.asyncio
async def test_report_schedule_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/reports/schedules",
            headers=headers,
            json={**_BASE, "name": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/reports/schedules",
        headers=headers,
        json={**_BASE, "name": f"  Tip120 name {suffix}  "},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["name"] == f"Tip120 name {suffix}"
    schedule_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/reports/schedules/{schedule_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/reports/schedules/{schedule_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
