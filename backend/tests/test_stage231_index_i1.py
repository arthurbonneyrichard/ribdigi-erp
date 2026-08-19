"""Stage 231 I1 — PITR drill pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pitr-drill-pack-remaining-gate.json"


def test_pitr_drill_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 231 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_pitr_drill_claimed"] is False
    assert data["ci_pitr_replay_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["live_dr_claimed"] is False
    assert data["distinct_from_stage28_r1_pitr_drill_pack"] is True
    assert data["distinct_from_stage192_live_dr_remaining_gate"] is True
    assert data["distinct_from_stage230_launch_cert_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pdpr-drill-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pitr_drill_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/PITR_DRILL_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_pitr_drill_claimed" in doc
    assert "PITR_DRILL_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "PITR_DRILL_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 28" in doc
    assert "Stage 192" in doc
