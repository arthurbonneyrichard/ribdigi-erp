"""Stage 319 I1 — backup restore drill honesty pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "backup-restore-drill-honesty-pack-remaining-gate.json"


def test_backup_restore_drill_honesty_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 319 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_backup_restore_claimed"] is False
    assert data["e2e_smoke_executed_claimed"] is False
    assert data["live_pitr_drill_claimed"] is False
    assert data["demo_tenant_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage169_backup_restore_drill_honesty"] is True
    assert data["distinct_from_pitr_drill_pack_remaining_gate"] is True
    assert data["distinct_from_stage318_k8s_deploy_pack_remaining_gate"] is True
    assert data["distinct_from_stage317_pgbouncer_soak_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "brdhr-backup-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_backup_restore_drill_honesty_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/BACKUP_RESTORE_DRILL_HONESTY_PACK_REMAINING_GATE_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "live_backup_restore_claimed" in doc
    assert "live_pitr_drill_claimed" in doc
    assert "BACKUP_RESTORE_DRILL_HONESTY_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "BACKUP_RESTORE_DRILL_HONESTY_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 169" in doc
    assert "BACKUP_RESTORE_DRILL_HONESTY_MVP.md" in doc
    assert "PITR_DRILL_PACK_REMAINING_GATE_MVP.md" in doc
