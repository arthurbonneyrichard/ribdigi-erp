"""Stage 233 P1 — WAL offsite RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "wal-offsite-rg-pointers.json"


def test_wal_offsite_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 233 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_offsite_backup_claimed"] is False
    assert data["live_wal_archive_claimed"] is False
    for topic in (
        "wal_pitr_runbook_stage26_w1",
        "backup_offsite_upload_stage27_b1",
        "pitr_drill_pack_remaining_gate_stage231",
        "ar_ap_accounting_surface_stage232",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "worp-offsite-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_wal_offsite_rg_pointers_doc_p1():
    doc = (ROOT / "docs/WAL_OFFSITE_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "DR_WAL_PITR_RUNBOOK.md" in doc
    assert "PITR_DRILL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "AR_AP_ACCOUNTING_SURFACE_MVP.md" in doc
    assert "live_offsite_backup_claimed" in doc
