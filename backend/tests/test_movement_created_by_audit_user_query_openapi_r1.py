"""Movement created_by + audit user_id Query ∈ UuidIdValue OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_MV_PATHS = ("/api/v1/inventory/movements", "/api/v1/reports/inventory/movements")
_AUDIT_PATHS = ("/api/v1/audit-logs", "/api/v1/audit-logs/export")


def test_created_by_user_id_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_created_by_user_id_query_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Movement created_by Query OpenAPI" in agents
    assert "Audit user_id Query OpenAPI" in agents
    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Audit user filter"' in audit
    assert "params.set('user_id', userTrim)" in audit


@pytest.mark.asyncio
async def test_movement_created_by_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _MV_PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
            resp = await ac.get(f"{path}?created_by={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?created_by={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422


@pytest.mark.asyncio
async def test_audit_user_id_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _AUDIT_PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
            resp = await ac.get(f"{path}?user_id={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?user_id={str(uuid4()).upper()}",
            headers=headers,
        )
        # export returns CSV file on 200; list returns JSON
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
