"""Stage 101 P1 — POS session history discoverability."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_shell_and_pos_session_history_ui_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "POS Sessions" in shell
    assert "/pos#sessions" in shell

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'id="sessions"' in pos
    assert "sessionHistory" in pos
    assert "/pos/sessions" in pos
    assert "viewShiftReport" in pos or "/report" in pos
    assert "scrollIntoView" in pos

    dash = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "/pos#sessions" in dash


@pytest.mark.asyncio
async def test_pos_sessions_list_api(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/pos/sessions", headers=headers)
    assert r.status_code == 200, r.text
    assert isinstance(r.json().get("data"), list)
