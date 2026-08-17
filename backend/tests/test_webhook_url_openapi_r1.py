"""Webhook endpoint URL OpenAPI honesty (BR-18.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import WebhookCreate, WebhookUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_webhook_url_schema():
    ok = WebhookCreate.model_validate(
        {
            "url": "  https://example.com/hooks  ",
            "events": ["webhook.test"],
        }
    )
    assert ok.url == "https://example.com/hooks"

    local = WebhookCreate.model_validate(
        {
            "url": "http://localhost:9999/hook",
            "events": ["webhook.test"],
        }
    )
    assert local.url.startswith("http://localhost")

    for bad in (
        "",
        " ",
        "not-a-url",
        "ftp://example.com/x",
        "http://example.com/hooks",
        "example.com/hooks",
    ):
        with pytest.raises(ValidationError):
            WebhookCreate.model_validate({"url": bad, "events": ["webhook.test"]})

    bare = WebhookUpdate.model_validate({})
    assert bare.url is None
    with pytest.raises(ValidationError):
        WebhookUpdate.model_validate({"url": ""})
    with pytest.raises(ValidationError):
        WebhookUpdate.model_validate({"url": "ftp://x"})


def test_webhook_url_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Webhook endpoint URL"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Webhook URL OpenAPI" in agents
    assert "WebhookUrlValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "WebhookUrlValue" in docs
    assert "Webhook endpoint URL" in docs


@pytest.mark.asyncio
async def test_webhook_url_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "not-a-url", "ftp://example.com/x", "http://example.com/hooks"):
        resp = await ac.post(
            "/api/v1/webhooks",
            headers=headers,
            json={"url": bad, "events": ["webhook.test"]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/webhooks/ribdigi-openapi",
            "events": ["webhook.test"],
            "description": f"url-honest-{uuid4().hex[:6]}",
        },
    )
    assert ok.status_code == 200, ok.text
    wid = ok.json()["data"]["id"]
    assert ok.json()["data"]["url"].startswith("https://")

    patch_bad = await ac.patch(
        f"/api/v1/webhooks/{wid}",
        headers=headers,
        json={"url": "ftp://example.com/x"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    deleted = await ac.delete(f"/api/v1/webhooks/{wid}", headers=headers)
    assert deleted.status_code == 200, deleted.text
