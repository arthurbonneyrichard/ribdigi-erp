"""Stage 199 P1 — first commercial day pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-commercial-day-pack-pointers.json"


def test_first_commercial_day_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 199 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["first_commercial_day_claimed"] is False
    assert data["commercial_day_ops_live_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "first_commercial_day_stage70",
        "commercial_golive_closeout_stage70",
        "steady_state_ops_remaining_gate_stage198",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "fp-day-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_commercial_day_pack_pointers_doc_p1():
    doc = (ROOT / "docs/FIRST_COMMERCIAL_DAY_PACK_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "FIRST_COMMERCIAL_DAY_MVP.md" in doc
    assert "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in doc
    assert "STEADY_STATE_OPS_REMAINING_GATE_MVP.md" in doc
    assert "first_commercial_day_claimed" in doc
