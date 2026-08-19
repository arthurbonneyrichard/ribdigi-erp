"""Stage 185 P1 — schema-per-tenant pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "schema-per-tenant-pack-pointers.json"


def test_schema_per_tenant_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 185 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["schema_per_tenant_claimed"] is False
    assert data["database_per_tenant_claimed"] is False
    assert data["shared_schema_as_schema_per_tenant_claimed"] is False
    for topic in (
        "adr001_tenancy",
        "deferred_adr_register",
        "production_readiness",
        "i18n_remaining_gate_stage184",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sp-schema-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_schema_per_tenant_pack_pointers_doc_p1():
    doc = (ROOT / "docs/SCHEMA_PER_TENANT_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_001_TENANCY.md" in doc
    assert "DEFERRED_ADR_REGISTER_MVP.md" in doc
    assert "PRODUCTION_READINESS.md" in doc
    assert "schema_per_tenant_claimed" in doc
