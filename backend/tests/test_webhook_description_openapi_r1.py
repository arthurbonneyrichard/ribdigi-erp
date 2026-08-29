"""WebhookCreate / WebhookUpdate.description OpenAPI honesty (BR-18.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import WebhookCreate, WebhookUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_webhook_description_schema():
    omit = WebhookCreate.model_validate(
        {"url": "https://example.com/hooks", "events": ["webhook.test"]}
    )
    assert omit.description is None
    nullish = WebhookCreate.model_validate(
        {
            "url": "https://example.com/hooks",
            "events": ["webhook.test"],
            "description": None,
        }
    )
    assert nullish.description is None
    ok = WebhookCreate.model_validate(
        {
            "url": "https://example.com/hooks",
            "events": ["webhook.test"],
            "description": "  Ops alert hook  ",
        }
    )
    assert ok.description == "Ops alert hook"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            WebhookCreate.model_validate(
                {
                    "url": "https://example.com/hooks",
                    "events": ["webhook.test"],
                    "description": bad,
                }
            )

    patch_omit = WebhookUpdate.model_validate({})
    assert patch_omit.description is None
    patch_ok = WebhookUpdate.model_validate({"description": " Renamed "})
    assert patch_ok.description == "Renamed"
    with pytest.raises(ValidationError):
        WebhookUpdate.model_validate({"description": "!!!"})
    with pytest.raises(ValidationError):
        WebhookUpdate.model_validate({"description": "  "})


def test_webhook_description_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Webhook description"' in page
    assert "hookDesc.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Webhook description OpenAPI" in agents
    assert "WebhookDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "WebhookDescriptionValue" in docs
    assert "Webhook description" in docs


@pytest.mark.asyncio
async def test_webhook_description_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    url = f"https://example.com/hooks/{suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/webhooks",
            headers=headers,
            json={"url": url, "events": ["webhook.test"], "description": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={"url": f"{url}-omit", "events": ["webhook.test"]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["description"] is None

    ok = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": f"{url}-ok",
            "events": ["webhook.test"],
            "description": f"  Tip144 Hook {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["description"] == f"Tip144 Hook {suffix}"
    wid = ok.json()["data"]["id"]

    keep = await ac.patch(
        f"/api/v1/webhooks/{wid}",
        headers=headers,
        json={"is_active": True},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["description"] == f"Tip144 Hook {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/webhooks/{wid}",
            headers=headers,
            json={"description": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/webhooks/{wid}",
        headers=headers,
        json={"description": f"  Tip144 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["description"] == f"Tip144 Renamed {suffix}"
