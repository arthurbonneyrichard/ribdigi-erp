"""Stage 322 P1 — live migration pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-migration-pack-rg-pointers.json"


def test_live_migration_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 322 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_migration_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "live_migration_remaining_gate_stage193",
        "live_dr_pack_remaining_gate_stage321",
        "e2e_backup_restore_pack_remaining_gate_stage320",
        "first_tenant_live_onboarding_remaining_gate_stage194",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lmprp-migration-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_migration_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LIVE_MIGRATION_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LIVE_MIGRATION_REMAINING_GATE_MVP.md" in doc
    assert "LIVE_DR_PACK_REMAINING_GATE_MVP.md" in doc
    assert "E2E_BACKUP_RESTORE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_REMAINING_GATE_MVP.md" in doc
    assert "live_migration_claimed" in doc
    assert "production_migrate_claimed" in doc
