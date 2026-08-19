"""Stage 270 B1 — Shared-schema tenancy pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "shared-schema-tenancy-pack-rg-blockers.json"


def test_shared_schema_tenancy_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 270 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["schema_per_tenant_complete"] == "REMAINING"
    assert blockers["live_multitenant_complete"] == "REMAINING"
    assert blockers["adr001_as_schema_per_tenant_complete"] == "NON_CLAIM"
    assert blockers["billing_complete_claimed"] == "false"
    assert blockers["schema_per_tenant_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sstprb-tenancy-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_shared_schema_tenancy_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SHARED_SCHEMA_TENANCY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "schema_per_tenant_claimed" in doc
    assert "ADR-001" in doc or "ADR_001" in doc
