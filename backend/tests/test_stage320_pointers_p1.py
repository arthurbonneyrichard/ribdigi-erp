"""Stage 320 P1 — E2E backup restore pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-backup-restore-pack-rg-pointers.json"


def test_e2e_backup_restore_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 320 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_backup_restore_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "e2e_backup_restore_stage35",
        "backup_restore_drill_honesty_pack_remaining_gate_stage319",
        "k8s_deploy_pack_remaining_gate_stage318",
        "live_dr_remaining_gate_stage192",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ebrprp-e2e-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_e2e_backup_restore_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/E2E_BACKUP_RESTORE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "E2E_BACKUP_RESTORE_MVP.md" in doc
    assert "BACKUP_RESTORE_DRILL_HONESTY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "K8S_DEPLOY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "LIVE_DR_REMAINING_GATE_MVP.md" in doc
    assert "live_backup_restore_claimed" in doc
    assert "e2e_smoke_executed_claimed" in doc
