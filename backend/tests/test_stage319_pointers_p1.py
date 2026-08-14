"""Stage 319 P1 — backup restore drill honesty pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "backup-restore-drill-honesty-pack-rg-pointers.json"


def test_backup_restore_drill_honesty_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 319 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_backup_restore_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "backup_restore_drill_honesty_stage169",
        "k8s_deploy_pack_remaining_gate_stage318",
        "pgbouncer_soak_pack_remaining_gate_stage317",
        "pitr_drill_pack_remaining_gate",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "brdhrp-backup-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_backup_restore_drill_honesty_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/BACKUP_RESTORE_DRILL_HONESTY_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "BACKUP_RESTORE_DRILL_HONESTY_MVP.md" in doc
    assert "K8S_DEPLOY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PGBOUNCER_SOAK_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PITR_DRILL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_backup_restore_claimed" in doc
    assert "live_pitr_drill_claimed" in doc
