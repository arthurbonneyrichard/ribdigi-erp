"""OpenAPI honesty tip #495: auth session Path session_id ∈ UuidIdValue."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_auth_session_path_session_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Auth session path session_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "DELETE /auth/sessions/{session_id}" in docs
    assert "UuidIdValue" in docs
    sec = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={s.current ? \'Sign out this device\' : \'Revoke session\'}' in sec
    assert "String(s.id).trim()" in sec
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "async def revoke_session(" in api
    assert "session_id: UuidIdValue," in api.split("async def revoke_session(", 1)[1][:200]


@pytest.mark.asyncio
async def test_auth_session_path_session_id_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for bad in ("!!!", "nonexistent", "not-a-uuid", "sess_001"):
        resp = await ac.delete(f"/api/v1/auth/sessions/{bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)
    missing = await ac.delete(f"/api/v1/auth/sessions/{uuid4()}", headers=headers)
    assert missing.status_code == 404, missing.text
