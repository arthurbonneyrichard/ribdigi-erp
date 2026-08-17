"""Bank connection feed_url OpenAPI honesty (BR-10.3) — reuse WebhookUrlValue."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import BankConnectionCreate, BankConnectionUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_feed_url_schema():
    ok = BankConnectionCreate.model_validate(
        {
            "account_id": "a1",
            "provider": "http_json",
            "feed_url": "  https://example.com/transactions  ",
        }
    )
    assert ok.feed_url == "https://example.com/transactions"

    local = BankConnectionCreate.model_validate(
        {
            "account_id": "a1",
            "provider": "http_json",
            "feed_url": "http://localhost:9999/feed",
        }
    )
    assert local.feed_url.startswith("http://localhost")

    bare = BankConnectionCreate.model_validate({"account_id": "a1"})
    assert bare.feed_url is None

    for bad in (
        "",
        " ",
        "not-a-url",
        "ftp://example.com/x",
        "http://example.com/feed",
        "example.com/feed",
    ):
        with pytest.raises(ValidationError):
            BankConnectionCreate.model_validate(
                {"account_id": "a1", "provider": "http_json", "feed_url": bad}
            )

    upd = BankConnectionUpdate.model_validate({})
    assert upd.feed_url is None
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"feed_url": ""})
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"feed_url": "ftp://x"})


def test_bank_feed_url_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank feed URL"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank feed URL OpenAPI" in agents
    assert "WebhookUrlValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "WebhookUrlValue" in docs
    assert "Bank feed URL" in docs


@pytest.mark.asyncio
async def test_bank_feed_url_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()[
        "data"
    ]
    assert accounts, "expected seeded liquid accounts"
    account_id = accounts[0]["id"]

    for bad in ("", "not-a-url", "ftp://example.com/x", "http://example.com/feed"):
        resp = await ac.post(
            "/api/v1/accounting/bank-connections",
            headers=headers,
            json={
                "account_id": account_id,
                "provider": "http_json",
                "feed_url": bad,
                "display_name": f"bad-{uuid4().hex[:6]}",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    # Missing feed_url on http_json remains service 400 (required), not schema 422.
    missing = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={"account_id": account_id, "provider": "http_json"},
    )
    assert missing.status_code == 400, missing.text

    ok = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": account_id,
            "provider": "http_json",
            "feed_url": "https://example.com/bank-feeds/openapi-honesty",
            "display_name": f"feed-honest-{uuid4().hex[:6]}",
            "auto_sync": False,
            "auto_match_after_sync": False,
        },
    )
    assert ok.status_code == 200, ok.text
    cid = ok.json()["data"]["id"]
    assert ok.json()["data"]["feed_url"].startswith("https://")

    patch_bad = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"feed_url": "ftp://example.com/x"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    deleted = await ac.delete(
        f"/api/v1/accounting/bank-connections/{cid}", headers=headers
    )
    assert deleted.status_code == 200, deleted.text
