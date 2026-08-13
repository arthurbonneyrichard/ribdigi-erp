"""Stage 225 B1 — loadtest baseline blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "loadtest-baseline-blockers.json"


def test_loadtest_baseline_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 225 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["certified_load_claimed"] is False
    assert data["live_load_capacity_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["certified_staging_load_run"] == "REMAINING"
    assert blockers["live_sized_staging_capacity"] == "REMAINING"
    assert blockers["stage5_l1_stage18_t1_as_certified_load"] == "NON_CLAIM"
    assert blockers["certified_load_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ltbb-certified-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_loadtest_baseline_blockers_doc_b1():
    doc = (ROOT / "docs/LOADTEST_BASELINE_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "certified_load_claimed" in doc
    assert "Stage 5" in doc
