"""Stage 231 P1 — PITR drill pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pitr-drill-pack-rg-pointers.json"


def test_pitr_drill_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 231 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_pitr_drill_claimed"] is False
    assert data["ci_pitr_replay_claimed"] is False
    for topic in (
        "pitr_drill_pack_stage28_r1",
        "wal_pitr_runbook_stage26_w1",
        "live_dr_remaining_gate_stage192",
        "launch_cert_pack_remaining_gate_stage230",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pdprp-drill-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pitr_drill_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PITR_DRILL_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PITR_DRILL_PACK_MVP.md" in doc
    assert "LIVE_DR_REMAINING_GATE_MVP.md" in doc
    assert "LAUNCH_CERT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_pitr_drill_claimed" in doc
