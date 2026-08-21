"""WebhookCreate.secret ∈ WebhookSecretValue OpenAPI honesty (BR-18.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import WebhookCreate, WebhookSecretValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(WebhookSecretValue)


def test_webhook_secret_value_schema():
    assert _token.validate_python("  Tip251WebhookSecret!  ") == "Tip251WebhookSecret!"
    assert _token.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "sec ret", "a" * 129):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    omit = WebhookCreate.model_validate(
        {"url": "https://example.com/hooks", "events": ["webhook.test"]}
    )
    assert omit.secret is None
    ok = WebhookCreate.model_validate(
        {
            "url": "https://example.com/hooks",
            "events": ["webhook.test"],
            "secret": "  Tip251WebhookSecret!  ",
        }
    )
    assert ok.secret == "Tip251WebhookSecret!"
    for bad in ("", "!!!", "http://evil", "a@b", "sec ret"):
        with pytest.raises(ValidationError):
            WebhookCreate.model_validate(
                {
                    "url": "https://example.com/hooks",
                    "events": ["webhook.test"],
                    "secret": bad,
                }
            )


def test_webhook_secret_ui_and_docs():
    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Webhook signing secret"' in integrations
    assert "hookSecret" in integrations
    assert "secret: hookSecret.trim() || null" in integrations
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Webhook secret OpenAPI" in agents
    assert "WebhookSecretValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "WebhookSecretValue" in docs
    assert "Webhook signing secret" in docs


@pytest.mark.asyncio
async def test_webhook_secret_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    base = {
        "url": f"https://example.com/hooks/tip251-{suffix}",
        "events": ["webhook.test"],
        "description": f"Tip251 hook {suffix}",
    }

    for bad in ("", "!!!", "http://evil", "a@b", "sec ret"):
        resp = await ac.post(
            "/api/v1/webhooks",
            headers=headers,
            json={**base, "url": f"{base['url']}-bad-{abs(hash(bad)) % 10000}", "secret": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post("/api/v1/webhooks", headers=headers, json=base)
    assert omit.status_code == 200, omit.text
    omit_body = omit.json()["data"]
    assert omit_body.get("secret", "").startswith("whsec_")
    assert omit_body.get("secret_shown_once") is True

    custom = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            **base,
            "url": f"https://example.com/hooks/tip251-custom-{suffix}",
            "secret": "  Tip251WebhookSecret!  ",
            "description": f"Tip251 custom {suffix}",
        },
    )
    assert custom.status_code == 200, custom.text
    custom_body = custom.json()["data"]
    assert custom_body.get("secret") == "Tip251WebhookSecret!"
    assert custom_body.get("secret_shown_once") is True
