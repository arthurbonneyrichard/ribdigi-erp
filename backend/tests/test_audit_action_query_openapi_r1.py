"""Audit logs action Query OpenAPI honesty (BR-17) — shape-only (2fa_* OK)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AuditActionValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_audit_action_schema():
    adapter = TypeAdapter(AuditActionValue)
    assert adapter.validate_python("  Login ") == "login"
    assert adapter.validate_python("2fa_failed") == "2fa_failed"
    assert adapter.validate_python("2FA_Enabled") == "2fa_enabled"
    assert adapter.validate_python("bank_connection_create") == "bank_connection_create"
    for bad in ("", " ", "A", "login!", "Login!", "!!!", "a", "login space"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_audit_action_ui_and_docs():
    page = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Audit action filter"' in page
    assert "auditActionQueryValue" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Audit action Query OpenAPI" in agents
    assert "AuditActionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AuditActionValue" in docs
    assert "Audit action filter" in docs


@pytest.mark.asyncio
async def test_audit_action_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/audit-logs?action=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/audit-logs?action=login!", headers=headers)
    assert bad.status_code == 422, bad.text

    short = await ac.get("/api/v1/audit-logs?action=A", headers=headers)
    assert short.status_code == 422, short.text

    export_bad = await ac.get(
        "/api/v1/audit-logs/export?action=!!!",
        headers=headers,
    )
    assert export_bad.status_code == 422, export_bad.text

    ok_login = await ac.get("/api/v1/audit-logs?action=login&limit=5", headers=headers)
    assert ok_login.status_code == 200, ok_login.text
    assert isinstance(ok_login.json()["data"], list)

    ok_2fa = await ac.get("/api/v1/audit-logs?action=2fa_failed&limit=5", headers=headers)
    assert ok_2fa.status_code == 200, ok_2fa.text

    # Well-shaped unknown action → empty list (not 422).
    unknown = await ac.get(
        "/api/v1/audit-logs?action=definitely_not_an_action&limit=5",
        headers=headers,
    )
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["data"] == []

    omit = await ac.get("/api/v1/audit-logs?limit=1", headers=headers)
    assert omit.status_code == 200, omit.text
