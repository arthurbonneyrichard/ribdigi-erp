"""Stage 203 B1 — cutover blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cutover-blockers.json"


def test_cutover_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 203 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["production_cutover_claimed"] is False
    assert data["section_7_signed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_production_cutover_execution"] == "REMAINING"
    assert blockers["section_7_signed"] == "REMAINING"
    assert blockers["stage29_x1_as_live_production_cutover"] == "NON_CLAIM"
    assert blockers["stage27_l1_as_live_production_cutover"] == "NON_CLAIM"
    assert blockers["production_cutover_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cb-cutover-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cutover_blockers_doc_b1():
    doc = (ROOT / "docs/CUTOVER_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "production_cutover_claimed" in doc
    assert "Stage 29" in doc
    assert "Stage 27" in doc
