"""The software owner edits the public legal pages in the console (15 Nov 2026)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio

BODY = "## Who we are\n\nRibdigi House runs RIBDIGI ERP.\n\n- one\n- two\n"


async def test_public_page_is_null_until_something_is_published(client):
    ac, _seed = client
    r = await ac.get("/api/v1/legal/privacy")
    assert r.status_code == 200 and r.json()["data"] is None
    assert (await ac.get("/api/v1/legal/unknown")).status_code == 422


async def test_owner_saves_draft_then_publishes_and_history_is_kept(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)

    draft = await ac.post(
        "/api/v1/platform/legal/terms",
        json={"title": "Terms of Service", "body": BODY, "effective_date": "2026-12-01", "note": "First pass"},
        headers=owner,
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["data"]["status"] == "draft" and draft.json()["data"]["version"] == 1
    # A draft is not public.
    assert (await ac.get("/api/v1/legal/terms")).json()["data"] is None

    pub = await ac.post(
        "/api/v1/platform/legal/terms",
        json={"title": "Terms of Service", "body": BODY + "\nMore.", "publish": True},
        headers=owner,
    )
    assert pub.json()["data"]["version"] == 2
    public = (await ac.get("/api/v1/legal/terms")).json()["data"]
    assert public["version"] == 2 and public["body"].endswith("More.")

    # Bring version 1 back: saved as a new published version 3, nothing overwritten.
    back = await ac.post("/api/v1/platform/legal/terms/versions/1/publish", headers=owner)
    assert back.status_code == 200 and back.json()["data"]["version"] == 3
    assert (await ac.get("/api/v1/legal/terms")).json()["data"]["body"] == BODY.strip()

    doc = (await ac.get("/api/v1/platform/legal/terms", headers=owner)).json()["data"]
    assert [v["version"] for v in doc["versions"]] == [3, 2, 1]
    listing = (await ac.get("/api/v1/platform/legal", headers=owner)).json()["data"]
    terms = next(x for x in listing if x["slug"] == "terms")
    assert terms["published"]["version"] == 3 and terms["draft"] is None


async def test_company_admin_cannot_edit_or_read_console_and_bad_input_is_refused(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/platform/legal", headers=admin)).status_code == 403
    r = await ac.post("/api/v1/platform/legal/privacy", json={"title": "Privacy", "body": BODY}, headers=admin)
    assert r.status_code == 403

    owner = await platform_owner_headers(ac, seed)
    short = await ac.post("/api/v1/platform/legal/privacy", json={"title": "P", "body": "x"}, headers=owner)
    assert short.status_code == 422
    extra = await ac.post(
        "/api/v1/platform/legal/privacy", json={"title": "Privacy", "body": BODY, "html": "<b>"}, headers=owner
    )
    assert extra.status_code == 422
