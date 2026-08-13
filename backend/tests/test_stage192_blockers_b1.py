"""Stage 192 B1 — live DR blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-dr-blockers.json"


def test_live_dr_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 192 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_dr_claimed"] is False
    assert data["live_backup_restore_claimed"] is False
    assert data["live_pitr_drill_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_dr_execution"] == "REMAINING"
    assert blockers["live_staging_restore"] == "REMAINING"
    assert blockers["live_pitr_drill"] == "REMAINING"
    assert blockers["stage169_b1_as_live_dr"] == "NON_CLAIM"
    assert blockers["stage35_r1_as_live_dr"] == "NON_CLAIM"
    assert blockers["live_dr_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lb-dr-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_dr_blockers_doc_b1():
    doc = (ROOT / "docs/LIVE_DR_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_dr_claimed" in doc
    assert "Stage 169" in doc
    assert "PITR" in doc or "pitr" in doc.lower()
