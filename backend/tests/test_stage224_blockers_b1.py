"""Stage 224 B1 — load capacity blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "load-capacity-blockers.json"


def test_load_capacity_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 224 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_load_capacity_claimed"] is False
    assert data["operator_1000vu_executed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_sized_staging_capacity"] == "REMAINING"
    assert blockers["operator_staging_1000vu_execution"] == "REMAINING"
    assert blockers["stage26_c1_as_live_capacity"] == "NON_CLAIM"
    assert blockers["live_load_capacity_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lcapb-live-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_load_capacity_blockers_doc_b1():
    doc = (ROOT / "docs/LOAD_CAPACITY_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_load_capacity_claimed" in doc
    assert "Stage 26" in doc
