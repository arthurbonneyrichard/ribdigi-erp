"""Stage 321 B1 — live DR pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-dr-pack-rg-blockers.json"


def test_live_dr_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 321 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_dr_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_dr_claimed"] == "REMAINING"
    assert blockers["live_backup_restore_claimed"] == "REMAINING"
    assert blockers["live_pitr_drill_claimed"] == "REMAINING"
    assert blockers["live_migration_claimed"] == "REMAINING"
    assert blockers["stage192_as_live_dr"] == "NON_CLAIM"
    assert blockers["live_dr_claimed_flag"] == "false"
    assert blockers["live_pitr_drill_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ldprb-dr-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_dr_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LIVE_DR_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_dr_claimed" in doc
    assert "live_pitr_drill_claimed" in doc
    assert "Stage 192" in doc
