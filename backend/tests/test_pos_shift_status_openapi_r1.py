"""GET /pos/sessions status Query OpenAPI + POS Recent shifts filter (BR-8.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PosSessionStatusFilterValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_shift_status_literal_schema():
    adapter = TypeAdapter(PosSessionStatusFilterValue)
    assert adapter.validate_python("open") == "open"
    assert adapter.validate_python("  Closed ") == "closed"
    assert adapter.validate_python("OPEN") == "open"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("balanced")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_pos_shift_status_ui_and_docs():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "shiftManageFilter" in page
    assert "managedShifts" in page
    assert 'aria-label="POS shift status filter"' in page
    assert 'value="open"' in page
    assert 'value="closed"' in page
    assert "No shifts for this filter" in page
    assert "Recent shifts" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS shift status Query OpenAPI" in agents
    assert "shiftManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "shiftManageFilter" in docs
    assert "GET /pos/sessions" in docs
    assert "open" in docs and "closed" in docs


@pytest.mark.asyncio
async def test_pos_shift_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/pos/sessions?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/pos/sessions?status=balanced", headers=headers)
    assert bad.status_code == 422, bad.text

    # Close any existing open shift for this user so we can open a fresh one.
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert cur.status_code == 200, cur.text
    current = cur.json().get("data")
    if current and current.get("session_id"):
        closed = await ac.post(
            f"/api/v1/pos/sessions/{current['session_id']}/close",
            headers=headers,
            json={"actual_cash": float(current.get("expected_cash") or 0)},
        )
        assert closed.status_code == 200, closed.text

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    open_id = opened.json()["data"]["session_id"]

    open_rows = await ac.get("/api/v1/pos/sessions?status=open", headers=headers)
    assert open_rows.status_code == 200, open_rows.text
    open_data = open_rows.json()["data"] or []
    assert open_data
    assert all(r.get("status") == "open" for r in open_data)
    assert any(r.get("session_id") == open_id for r in open_data)

    closed_again = await ac.post(
        f"/api/v1/pos/sessions/{open_id}/close",
        headers=headers,
        json={"actual_cash": 50, "notes": "shiftManageFilter hello-world"},
    )
    assert closed_again.status_code == 200, closed_again.text

    closed_rows = await ac.get("/api/v1/pos/sessions?status=closed", headers=headers)
    assert closed_rows.status_code == 200, closed_rows.text
    closed_data = closed_rows.json()["data"] or []
    assert closed_data
    assert all(r.get("status") == "closed" for r in closed_data)
    assert any(r.get("session_id") == open_id for r in closed_data)

    all_rows = await ac.get("/api/v1/pos/sessions", headers=headers)
    assert all_rows.status_code == 200, all_rows.text
    statuses = {r.get("status") for r in (all_rows.json()["data"] or [])}
    assert statuses <= {"open", "closed"}
    assert open_id in {r.get("session_id") for r in (all_rows.json()["data"] or [])}
