"""Store operating_hours typed body OpenAPI honesty (BR-2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import StoreDayHours, StoreOperatingHours, StoreUpdate
from app.stores import WEEKDAYS
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_store_operating_hours_schema():
    ok = StoreOperatingHours.model_validate(
        {
            "mon": {"open": "09:00", "close": "18:00"},
            "sat": {"closed": True},
        }
    )
    assert ok.mon is not None and ok.mon.open == "09:00"
    assert ok.sat is not None and ok.sat.closed is True

    stripped = StoreDayHours.model_validate({"open": " 08:30 ", "close": " 17:00 "})
    assert stripped.open == "08:30" and stripped.close == "17:00"

    with pytest.raises(ValidationError):
        StoreOperatingHours.model_validate(
            {"monday": {"open": "09:00", "close": "17:00"}}
        )
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "18:00", "close": "09:00"})
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "9:00", "close": "17:00"})
    with pytest.raises(ValidationError):
        StoreDayHours.model_validate({"open": "09:00", "close": "17:00", "extra": 1})
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate(
            {"operating_hours": {"mon": {"open": "", "close": "17:00"}}}
        )

    # Field names match WEEKDAYS
    assert set(StoreOperatingHours.model_fields.keys()) == set(WEEKDAYS)


def test_store_operating_hours_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "HoursEditor" in page
    assert 'aria-label={`Store ${label} open time`}' in page
    assert 'aria-label="Save store"' in page
    assert 'aria-label="Create store"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store operating_hours OpenAPI" in agents
    assert "StoreOperatingHours" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StoreOperatingHours" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_store_operating_hours_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": "OpenAPI Hours",
            "code": "OH-API",
            "operating_hours": {
                "mon": {"open": "09:00", "close": "17:00"},
                "sun": {"closed": True},
            },
        },
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]
    hours = created.json()["data"]["operating_hours"]
    assert hours["mon"]["open"] == "09:00"
    assert hours["sun"] == {"closed": True}

    bad_day = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"operating_hours": {"monday": {"open": "09:00", "close": "17:00"}}},
    )
    assert bad_day.status_code == 422, bad_day.text

    bad_order = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"operating_hours": {"mon": {"open": "18:00", "close": "09:00"}}},
    )
    assert bad_order.status_code == 422, bad_order.text

    ok = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={
            "operating_hours": {
                "mon": {"open": "08:00", "close": "20:00"},
                "tue": {"closed": True},
            }
        },
    )
    assert ok.status_code == 200, ok.text
    ph = ok.json()["data"]["operating_hours"]
    assert ph["mon"]["open"] == "08:00"
    assert ph["tue"] == {"closed": True}
