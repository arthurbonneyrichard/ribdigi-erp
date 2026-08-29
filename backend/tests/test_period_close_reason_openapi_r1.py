"""PeriodCloseBody / PeriodReopenBody.reason OpenAPI honesty (BR-10.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PeriodCloseBody, PeriodReopenBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_period_close_reason_schema():
    ok = PeriodCloseBody.model_validate(
        {"through_date": "2024-06-30", "reason": "  Month-end close  "}
    )
    assert ok.reason == "Month-end close"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PeriodCloseBody.model_validate({"through_date": "2024-06-30", "reason": bad})
    with pytest.raises(ValidationError):
        PeriodCloseBody.model_validate({"through_date": "2024-06-30"})

    reopen_ok = PeriodReopenBody.model_validate({"reason": "  Correction after close  "})
    assert reopen_ok.reason == "Correction after close"
    assert reopen_ok.through_date is None
    for bad in ("", " ", "!!!", "http://evil"):
        with pytest.raises(ValidationError):
            PeriodReopenBody.model_validate({"reason": bad})


def test_period_close_reason_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Period close or reopen reason"' in page
    assert 'aria-label="Close books"' in page
    assert 'aria-label="Reopen books"' in page
    assert "periodReason" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PeriodCloseReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PeriodCloseReasonValue" in docs


@pytest.mark.asyncio
async def test_period_close_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            "/api/v1/accounting/period/close",
            headers=headers,
            json={"through_date": yesterday, "reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday, "reason": "Tip204 month-end close — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["books_closed_through"] == yesterday

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            "/api/v1/accounting/period/reopen",
            headers=headers,
            json={"through_date": None, "reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    reopen = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": None, "reason": "Tip204 reopen after close — API hello-world"},
    )
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["data"]["books_closed_through"] is None
