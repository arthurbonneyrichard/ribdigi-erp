"""Stage 202 B1 — production launch blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "production-launch-blockers.json"


def test_production_launch_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 202 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["production_launch_live_claimed"] is False
    assert data["production_cutover_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_production_launch_execution"] == "REMAINING"
    assert blockers["production_cutover"] == "REMAINING"
    assert blockers["stage66_l1_as_live_production_launch"] == "NON_CLAIM"
    assert blockers["stage29_x1_as_live_production_launch"] == "NON_CLAIM"
    assert blockers["production_launch_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pb-launch-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_production_launch_blockers_doc_b1():
    doc = (ROOT / "docs/PRODUCTION_LAUNCH_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "production_launch_live_claimed" in doc
    assert "Stage 66" in doc
    assert "Stage 29" in doc
