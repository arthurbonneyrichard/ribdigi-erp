"""JournalUnpost.reason OpenAPI honesty (BR-10.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import JournalUnpost
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_journal_unpost_reason_schema():
    ok = JournalUnpost.model_validate({"reason": "  Duplicate entry  "})
    assert ok.reason == "Duplicate entry"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            JournalUnpost.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        JournalUnpost.model_validate({})


def test_journal_unpost_reason_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Journal unpost reason"' in page
    assert "unpostReason" in page
    assert "aria-label={`Unpost journal ${j.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "JournalUnpostReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "JournalUnpostReasonValue" in docs


@pytest.mark.asyncio
async def test_journal_unpost_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP202 unpost {suffix}"

    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    created = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": f"tip202 {suffix}",
            "lines": [
                {"account_code": "6000", "debit": 21, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 21},
            ],
        },
    )
    assert created.status_code == 200, created.text
    entry_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "unposted"
    assert f"Unpost: {tag}" in (body.get("description") or "")
