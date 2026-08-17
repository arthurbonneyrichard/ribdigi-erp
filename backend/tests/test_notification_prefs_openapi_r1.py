"""PATCH /notifications/settings typed preferences OpenAPI (BR-4.4 / BR-15.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.notifications import DEFAULT_PREFERENCES, VALID_CATEGORIES
from app.schemas import NotificationChannelPrefs, NotificationPreferencesMap, NotificationPreferencesUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_notification_preferences_map_covers_categories():
    fields = set(NotificationPreferencesMap.model_fields.keys())
    assert fields == set(DEFAULT_PREFERENCES.keys()) == VALID_CATEGORIES


def test_notification_channel_prefs_forbid_unknown():
    ok = NotificationChannelPrefs(dashboard=True, email=False, sms=False)
    assert ok.dashboard is True
    with pytest.raises(ValidationError):
        NotificationChannelPrefs(dashboard=True, push=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        NotificationPreferencesMap.model_validate({"not_a_category": {"dashboard": True}})
    with pytest.raises(ValidationError):
        NotificationPreferencesUpdate.model_validate(
            {"preferences": {"low_stock": {"dashboard": True, "webhook": False}}}
        )
    parsed = NotificationPreferencesUpdate.model_validate(
        {"preferences": {"low_stock": {"email": False}}}
    )
    assert parsed.preferences.low_stock is not None
    assert parsed.preferences.low_stock.email is False


def test_notification_preferences_ui_and_docs():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "Channel preferences" in page
    assert "togglePref" in page
    assert 'aria-label="Channel preferences"' in page
    assert "/notifications/settings" in page
    assert "preferences: next" in page or "{ preferences: next }" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Notification preferences OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "NotificationPreferencesMap" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_notification_preferences_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad_cat = await ac.patch(
        "/api/v1/notifications/settings",
        headers=headers,
        json={"preferences": {"not_a_real_category": {"dashboard": True}}},
    )
    assert bad_cat.status_code == 422, bad_cat.text

    bad_ch = await ac.patch(
        "/api/v1/notifications/settings",
        headers=headers,
        json={"preferences": {"low_stock": {"dashboard": True, "push": True}}},
    )
    assert bad_ch.status_code == 422, bad_ch.text

    # baseline get
    got = await ac.get("/api/v1/notifications/settings", headers=headers)
    assert got.status_code == 200, got.text
    prefs = got.json()["data"]
    assert "low_stock" in prefs

    # toggle email off for low_stock
    next_prefs = {**prefs, "low_stock": {**prefs["low_stock"], "email": not prefs["low_stock"]["email"]}}
    ok = await ac.patch(
        "/api/v1/notifications/settings",
        headers=headers,
        json={"preferences": next_prefs},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["low_stock"]["email"] == next_prefs["low_stock"]["email"]
