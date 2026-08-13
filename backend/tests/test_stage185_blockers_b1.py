"""Stage 185 B1 — schema-per-tenant blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "schema-per-tenant-blockers.json"


def test_schema_per_tenant_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 185 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["schema_per_tenant_claimed"] is False
    assert data["database_per_tenant_claimed"] is False
    assert data["shared_schema_as_schema_per_tenant_claimed"] is False
    blockers = data["blockers"]
    assert blockers["adr001_schema_per_tenant_migration"] == "DEFERRED"
    assert blockers["database_per_tenant"] == "REMAINING"
    assert blockers["per_tenant_backup_restore_isolation"] == "REMAINING"
    assert blockers["shared_schema_as_schema_per_tenant"] == "NON_CLAIM"
    assert blockers["schema_per_tenant_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sb-schema-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_schema_per_tenant_blockers_doc_b1():
    doc = (ROOT / "docs/SCHEMA_PER_TENANT_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR-001" in doc or "ADR_001" in doc
    assert "shared-schema" in doc.lower() or "shared_schema" in doc
    assert "schema-per-tenant" in doc.lower() or "schema_per_tenant" in doc
    assert "schema_per_tenant_claimed" in doc
