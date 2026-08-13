"""Stage 231 B1 — PITR drill pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pitr-drill-pack-rg-blockers.json"


def test_pitr_drill_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 231 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_pitr_drill_claimed"] is False
    assert data["ci_pitr_replay_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_staging_pitr_drill_execution"] == "REMAINING"
    assert blockers["ci_pitr_replay_certificate"] == "REMAINING"
    assert blockers["stage28_r1_as_live_pitr_drill"] == "NON_CLAIM"
    assert blockers["live_pitr_drill_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pdprb-drill-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pitr_drill_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/PITR_DRILL_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_pitr_drill_claimed" in doc
    assert "Stage 28" in doc
