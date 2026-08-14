"""Stage 270 P1 — Shared-schema tenancy pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "shared-schema-tenancy-pack-rg-pointers.json"


def test_shared_schema_tenancy_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 270 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "shared_schema_tenancy_adr001",
        "platform_principal_pack_remaining_gate_stage269",
        "dual_console_pack_remaining_gate_stage268",
        "schema_per_tenant_remaining_gate_stage185",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sstprp-tenancy-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_shared_schema_tenancy_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SHARED_SCHEMA_TENANCY_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_001_TENANCY.md" in doc
    assert "PLATFORM_PRINCIPAL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "DUAL_CONSOLE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SCHEMA_PER_TENANT_REMAINING_GATE_MVP.md" in doc
    assert "billing_complete_claimed" in doc
    assert "schema_per_tenant_claimed" in doc
