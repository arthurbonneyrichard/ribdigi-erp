"""Stage 258 P1 — steady-state ops pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "steady-state-ops-pack-rg-pointers.json"


def test_steady_state_ops_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 258 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["steady_state_ops_claimed"] is False
    assert data["first_commercial_day_claimed"] is False
    for topic in (
        "steady_state_ops_stage71_s1",
        "commercial_acceptance_pack_remaining_gate_stage257",
        "commercial_packaging_archive_pack_remaining_gate_stage256",
        "steady_state_ops_remaining_gate_stage198",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ssoprp-steady-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_steady_state_ops_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/STEADY_STATE_OPS_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "STEADY_STATE_OPS_MVP.md" in doc
    assert "COMMERCIAL_ACCEPTANCE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_PACKAGING_ARCHIVE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STEADY_STATE_OPS_REMAINING_GATE_MVP.md" in doc
    assert "steady_state_ops_claimed" in doc
    assert "first_commercial_day_claimed" in doc
