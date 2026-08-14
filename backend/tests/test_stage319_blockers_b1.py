"""Stage 319 B1 — backup restore drill honesty pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "backup-restore-drill-honesty-pack-rg-blockers.json"


def test_backup_restore_drill_honesty_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 319 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_backup_restore_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_backup_restore_claimed"] == "REMAINING"
    assert blockers["e2e_smoke_executed_claimed"] == "REMAINING"
    assert blockers["live_pitr_drill_claimed"] == "REMAINING"
    assert blockers["demo_tenant_claimed"] == "REMAINING"
    assert blockers["stage169_as_live_backup_restore"] == "NON_CLAIM"
    assert blockers["live_backup_restore_claimed_flag"] == "false"
    assert blockers["live_pitr_drill_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "brdhrb-backup-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_backup_restore_drill_honesty_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/BACKUP_RESTORE_DRILL_HONESTY_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "live_backup_restore_claimed" in doc
    assert "live_pitr_drill_claimed" in doc
    assert "Stage 169" in doc
