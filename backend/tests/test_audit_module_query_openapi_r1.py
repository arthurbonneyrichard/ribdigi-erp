"""Audit logs module Query OpenAPI honesty (BR-17)."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from app.audit import AUDIT_MODULES
from app.schemas import AuditModuleValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_audit_module_schema():
    adapter = TypeAdapter(AuditModuleValue)
    assert adapter.validate_python(" Auth ") == "auth"
    assert adapter.validate_python("USERS") == "users"
    for bad in ("", " ", "foobar", "AUTH!", "not_a_module"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)

    lit = get_args(AuditModuleValue)[0]
    assert set(get_args(lit)) == set(AUDIT_MODULES)


def test_audit_module_ui_and_docs():
    page = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Audit module filter"' in page
    assert "All modules" in page
    assert 'placeholder="Module (auth, users…)"' not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Audit module Query OpenAPI" in agents
    assert "AuditModuleValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AuditModuleValue" in docs
    assert "Audit module filter" in docs


@pytest.mark.asyncio
async def test_audit_module_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/audit-logs?module=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/audit-logs?module=not_a_module", headers=headers)
    assert bad.status_code == 422, bad.text

    export_bad = await ac.get("/api/v1/audit-logs/export?module=garbage", headers=headers)
    assert export_bad.status_code == 422, export_bad.text

    ok = await ac.get("/api/v1/audit-logs?module=auth", headers=headers)
    assert ok.status_code == 200, ok.text
    rows = ok.json()["data"]
    assert isinstance(rows, list)
    assert all(r.get("module") == "auth" for r in rows)

    omit = await ac.get("/api/v1/audit-logs", headers=headers)
    assert omit.status_code == 200, omit.text
