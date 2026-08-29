"""PosSessionClose.notes OpenAPI honesty (BR-8.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PosSessionClose
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_session_close_notes_schema():
    omit = PosSessionClose.model_validate({"actual_cash": 10})
    assert omit.notes is None
    ok = PosSessionClose.model_validate({"actual_cash": 10, "notes": "  Till balanced  "})
    assert ok.notes == "Till balanced"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PosSessionClose.model_validate({"actual_cash": 10, "notes": bad})


def test_pos_session_close_notes_ui_and_docs():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS shift close notes"' in page
    assert "closeNotes.trim() || null" in page
    assert 'aria-label="Close shift"' in page
    assert 'aria-label="Counted cash"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS shift close notes OpenAPI" in agents
    assert "PosSessionCloseNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PosSessionCloseNotesValue" in docs
    assert "POS shift close notes" in docs


async def _open_session(ac, headers):
    # Close any current open session first.
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and (cur.json().get("data") or {}).get("session_id"):
        sid = cur.json()["data"]["session_id"]
        await ac.post(
            f"/api/v1/pos/sessions/{sid}/close",
            headers=headers,
            json={"actual_cash": 0},
        )
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()["data"]


@pytest.mark.asyncio
async def test_pos_session_close_notes_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"Tip180 notes {suffix}"

    session = await _open_session(ac, headers)
    sid = session["session_id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            f"/api/v1/pos/sessions/{sid}/close",
            headers=headers,
            json={"actual_cash": 50, "notes": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=headers,
        json={"actual_cash": 50},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    session2 = await _open_session(ac, headers)
    sid2 = session2["session_id"]
    ok = await ac.post(
        f"/api/v1/pos/sessions/{sid2}/close",
        headers=headers,
        json={"actual_cash": 50, "notes": f"  {tag}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
