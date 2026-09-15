"""RecurringSkipNext.reason OpenAPI honesty (BR-9.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import RecurringSkipNext
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_recurring_skip_reason_schema():
    ok = RecurringSkipNext.model_validate({"reason": "  Holiday cycle  "})
    assert ok.reason == "Holiday cycle"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            RecurringSkipNext.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        RecurringSkipNext.model_validate({})


def test_recurring_skip_reason_ui_and_docs():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Skip next reason"' in page
    assert "skipNextReason" in page
    assert "JSON.stringify({ reason })" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "RecurringSkipReasonValue" in agents
    assert "Skip next reason" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "RecurringSkipReasonValue" in docs
    assert "Skip next reason" in docs


@pytest.mark.asyncio
async def test_recurring_skip_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cats = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]
    suffix = uuid4().hex[:8]
    tag = f"TIP190 skip {suffix}"

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "category_id": cat_id,
            "amount": 25,
            "frequency": "weekly",
            "description": f"Skip tip190 {suffix}",
            "payee": "Skip Tip190 Co",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]
    before = created.json()["data"]["next_run_at"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/expenses/recurring/{rid}/skip-next",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/expenses/recurring/{rid}/skip-next",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    after = ok.json()["data"]
    assert after["next_run_at"] > before
