"""StoreDayHours.open/close ∈ StoreHoursTimeValue OpenAPI (BR-2.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StoreDayHours, StoreHoursTimeValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_time = TypeAdapter(StoreHoursTimeValue)


def test_store_hours_time_value_schema():
    assert _time.validate_python("  09:00  ") == "09:00"
    assert _time.validate_python("23:59") == "23:59"
    assert _time.validate_python("00:00") == "00:00"
    for bad in ("", " ", "!!!", "9:00", "25:00", "12:60", "http://evil", "@@", "9:00am"):
        with pytest.raises(ValidationError):
            _time.validate_python(bad)

    closed = StoreDayHours.model_validate({"closed": True})
    assert closed.open is None and closed.close is None
    ok = StoreDayHours.model_validate({"open": "  08:30  ", "close": "17:45"})
    assert ok.open == "08:30" and ok.close == "17:45"
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "", "close": "17:00"})
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "!!!", "close": "17:00"})
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "18:00", "close": "09:00"})
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "09:00"})  # missing close when not closed
    # blank with closed still 422 on Value (honesty) — omit open instead
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"closed": True, "open": ""})


def test_store_hours_time_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Store ${label} open time`}' in page
    assert 'aria-label={`Store ${label} close time`}' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store hours open/close OpenAPI" in agents
    assert "StoreHoursTimeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StoreHoursTimeValue" in docs
    assert "Store {Day} open time" in docs


@pytest.mark.asyncio
async def test_store_hours_time_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:6]

    for bad_open in ("", "!!!", "9:00", "25:00", "http://evil.example"):
        bad = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={
                "name": f"Tip244 Bad {suffix}",
                "code": f"T244B{suffix}",
                "address": "1 Test Rd",
                "operating_hours": {"mon": {"open": bad_open, "close": "17:00"}},
            },
        )
        assert bad.status_code == 422, (bad_open, bad.text)

    ok = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": f"Tip244 Hours {suffix}",
            "code": f"T244H{suffix}",
            "address": "2 Test Rd",
            "operating_hours": {
                "mon": {"open": "  09:15  ", "close": "18:45"},
                "sat": {"closed": True},
            },
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["operating_hours"]["mon"]["open"] == "09:15"
    assert data["operating_hours"]["mon"]["close"] == "18:45"
    assert data["operating_hours"]["sat"] == {"closed": True}

    omit = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": f"Tip244 Omit {suffix}",
            "code": f"T244O{suffix}",
            "address": "3 Test Rd",
        },
    )
    assert omit.status_code == 200, omit.text
