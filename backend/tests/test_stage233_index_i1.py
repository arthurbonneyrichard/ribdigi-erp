"""Stage 233 I1 — WAL offsite remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "wal-offsite-remaining-gate.json"


def test_wal_offsite_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 233 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_offsite_backup_claimed"] is False
    assert data["live_wal_archive_claimed"] is False
    assert data["live_pitr_drill_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage26_w1_wal_pitr_strategy"] is True
    assert data["distinct_from_stage27_b1_backup_offsite"] is True
    assert data["distinct_from_stage231_pitr_drill_pack_remaining_gate"] is True
    assert data["distinct_from_stage232_ar_ap_accounting_surface"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "wor-offsite-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_wal_offsite_remaining_gate_doc_i1():
    doc = (ROOT / "docs/WAL_OFFSITE_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_offsite_backup_claimed" in doc
    assert "WAL_OFFSITE_RG_BLOCKERS_MVP.md" in doc
    assert "WAL_OFFSITE_RG_POINTERS_MVP.md" in doc
    assert "Stage 26" in doc
    assert "Stage 27" in doc
