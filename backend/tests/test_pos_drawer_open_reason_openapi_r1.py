"""PosDrawerOpen.reason OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PosDrawerOpen
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_drawer_open_reason_schema():
    ok = PosDrawerOpen.model_validate({"reason": "  Customer change request  "})
    assert ok.reason == "Customer change request"
    for bad in ("", " ", "ab", "!!!", "http://evil", "@@", "manual", "n/a", "test"):
        with pytest.raises(ValidationError):
            PosDrawerOpen.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        PosDrawerOpen.model_validate({})


def test_pos_drawer_open_reason_ui_and_docs():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash drawer open reason"' in page
    assert "drawerReason" in page
    assert 'aria-label="Open cash drawer"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PosDrawerOpenReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PosDrawerOpenReasonValue" in docs
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "PosDrawerOpenReasonValue" in brd


@pytest.mark.asyncio
async def test_pos_drawer_open_reason_api_blank_invalid_422(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.POS_DRAWER_FALLBACK_MODE", "mock")
    monkeypatch.setattr("app.cash_drawer.settings.POS_DRAWER_FALLBACK_MODE", "mock")

    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    for bad in ("", "!!!", "http://evil", "   ", "manual", "ab"):
        resp = await ac.post(
            f"/api/v1/pos/sessions/{session_id}/drawer/open",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/drawer/open",
        headers=headers,
        json={"reason": "Tip207 change for walk-in — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["ok"] is True
    assert body["reason"] == "Tip207 change for walk-in — API hello-world"
