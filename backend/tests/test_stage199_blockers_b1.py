"""Stage 199 B1 — first commercial day blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-commercial-day-blockers.json"


def test_first_commercial_day_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 199 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["first_commercial_day_claimed"] is False
    assert data["commercial_day_ops_live_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["first_commercial_day_live_execution"] == "REMAINING"
    assert blockers["commercial_golive_closeout"] == "REMAINING"
    assert blockers["stage70_f1_as_first_commercial_day_live"] == "NON_CLAIM"
    assert blockers["stage70_g1_as_first_commercial_day_live"] == "NON_CLAIM"
    assert blockers["first_commercial_day_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "fb-day-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_commercial_day_blockers_doc_b1():
    doc = (ROOT / "docs/FIRST_COMMERCIAL_DAY_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "first_commercial_day_claimed" in doc
    assert "Stage 70" in doc
