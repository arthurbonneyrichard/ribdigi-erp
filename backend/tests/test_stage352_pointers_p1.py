"""Stage 352 P1 — migration gate pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "migration-gate-pack-rg-pointers.json"


def test_migration_gate_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 352 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_migration_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "migration_gate_stage169",
        "quarterly_pos_ops_gates_pack_remaining_gate_stage351",
        "live_migration_pack_remaining_gate_stage322",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "mgprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_migration_gate_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/MIGRATION_GATE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "MIGRATION_GATE_MVP.md" in doc
    assert "QUARTERLY_POS_OPS_GATES_PACK_REMAINING_GATE_MVP.md" in doc
    assert "LIVE_MIGRATION_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_migration_claimed" in doc
    assert "production_migrate_claimed" in doc
