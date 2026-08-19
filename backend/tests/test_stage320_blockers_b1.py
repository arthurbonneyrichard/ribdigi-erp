"""Stage 320 B1 — E2E backup restore pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-backup-restore-pack-rg-blockers.json"


def test_e2e_backup_restore_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 320 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_backup_restore_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_backup_restore_claimed"] == "REMAINING"
    assert blockers["e2e_smoke_executed_claimed"] == "REMAINING"
    assert blockers["live_pitr_drill_claimed"] == "REMAINING"
    assert blockers["demo_tenant_claimed"] == "REMAINING"
    assert blockers["stage35_as_live_e2e_backup_restore"] == "NON_CLAIM"
    assert blockers["live_backup_restore_claimed_flag"] == "false"
    assert blockers["e2e_smoke_executed_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ebrprb-e2e-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_e2e_backup_restore_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/E2E_BACKUP_RESTORE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_backup_restore_claimed" in doc
    assert "e2e_smoke_executed_claimed" in doc
    assert "Stage 35" in doc
