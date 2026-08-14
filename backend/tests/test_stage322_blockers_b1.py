"""Stage 322 B1 — live migration pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-migration-pack-rg-blockers.json"


def test_live_migration_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 322 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_migration_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_migration_claimed"] == "REMAINING"
    assert blockers["production_migrate_claimed"] == "REMAINING"
    assert blockers["ci_deploy_claimed"] == "REMAINING"
    assert blockers["live_dr_claimed"] == "REMAINING"
    assert blockers["stage193_as_live_migration"] == "NON_CLAIM"
    assert blockers["live_migration_claimed_flag"] == "false"
    assert blockers["production_migrate_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lmprb-migration-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_migration_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LIVE_MIGRATION_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_migration_claimed" in doc
    assert "production_migrate_claimed" in doc
    assert "Stage 193" in doc
