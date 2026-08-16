"""Webhook events OpenAPI Literal."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.schemas import WebhookCreate, WebhookEventValue, WebhookUpdate
from app.webhooks import VALID_EVENTS

ROOT = Path(__file__).resolve().parents[2]


def test_webhook_events_literal_schema():
    ok = WebhookCreate.model_validate(
        {
            "url": "https://example.com/hooks",
            "events": ["Sale.Created", " webhook.test "],
        }
    )
    assert ok.events == ["sale.created", "webhook.test"]

    with pytest.raises(ValidationError):
        WebhookCreate.model_validate({"url": "https://example.com/hooks", "events": []})
    with pytest.raises(ValidationError):
        WebhookCreate.model_validate(
            {"url": "https://example.com/hooks", "events": ["sale.created", ""]}
        )
    with pytest.raises(ValidationError):
        WebhookCreate.model_validate(
            {"url": "https://example.com/hooks", "events": ["not.a.real.event"]}
        )

    patch = WebhookUpdate.model_validate({"events": ["STOCK.LOW"]})
    assert patch.events == ["stock.low"]
    with pytest.raises(ValidationError):
        WebhookUpdate.model_validate({"events": ["garbage"]})

    args = get_args(WebhookEventValue)
    lit = args[0] if args else None
    assert set(get_args(lit)) == set(VALID_EVENTS)


def test_webhook_events_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert "WEBHOOK_EVENTS" in page
    assert "sale.created" in page
    assert "webhook.test" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Webhook events OpenAPI" in agents
