"""Stage 260 P1 — commercial go-live closeout pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-golive-closeout-pack-rg-pointers.json"


def test_commercial_golive_closeout_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 260 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["commercial_golive_closeout_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "commercial_golive_closeout_stage70_g1",
        "first_commercial_day_pack_remaining_gate_stage259",
        "steady_state_ops_pack_remaining_gate_stage258",
        "commercial_golive_closeout_remaining_gate_stage200",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cgcprp-closeout-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_golive_closeout_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_GOLIVE_CLOSEOUT_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in doc
    assert "FIRST_COMMERCIAL_DAY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STEADY_STATE_OPS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_GOLIVE_CLOSEOUT_REMAINING_GATE_MVP.md" in doc
    assert "commercial_golive_closeout_claimed" in doc
    assert "go_live_claimed" in doc
