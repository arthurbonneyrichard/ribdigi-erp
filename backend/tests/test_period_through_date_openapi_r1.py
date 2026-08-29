"""PeriodCloseBody / PeriodReopenBody.through_date OpenAPI honesty (BR-10.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PeriodCloseBody, PeriodReopenBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_period_through_date_schema():
    base_reason = {"reason": "Month-end close"}
    ok = PeriodCloseBody.model_validate(
        {**base_reason, "through_date": " 2026-08-01 "}
    )
    assert ok.through_date == "2026-08-01"
    iso = PeriodCloseBody.model_validate(
        {**base_reason, "through_date": "2026-08-01T12:00:00"}
    )
    assert iso.through_date == "2026-08-01T12:00:00"
    with pytest.raises(ValidationError):
        PeriodCloseBody.model_validate({"reason": "x"})
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            PeriodCloseBody.model_validate({**base_reason, "through_date": bad})

    reopen_omit = PeriodReopenBody.model_validate(base_reason)
    assert reopen_omit.through_date is None
    reopen_ok = PeriodReopenBody.model_validate(
        {**base_reason, "through_date": "2026-07-01"}
    )
    assert reopen_ok.through_date == "2026-07-01"
    with pytest.raises(ValidationError):
        PeriodReopenBody.model_validate({**base_reason, "through_date": ""})
    with pytest.raises(ValidationError):
        PeriodReopenBody.model_validate({**base_reason, "through_date": "not-a-date"})


def test_period_through_date_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Period close through date"' in page
    assert "Through date YYYY-MM-DD" in page
    assert "through_date: closeThrough, reason" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Period through_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Period close through date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_period_through_date_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            "/api/v1/accounting/period/close",
            headers=headers,
            json={"through_date": bad, "reason": "tip117 bad close"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday, "reason": "tip117 valid close"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["books_closed_through"] == yesterday

    reopen_bad = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": "not-a-date", "reason": "tip117 bad reopen"},
    )
    assert reopen_bad.status_code == 422, reopen_bad.text

    clear = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": None, "reason": "tip117 clear reopen"},
    )
    assert clear.status_code == 200, clear.text
    assert clear.json()["data"]["books_closed_through"] is None
