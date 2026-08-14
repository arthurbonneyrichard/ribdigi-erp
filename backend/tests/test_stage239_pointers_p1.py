"""Stage 239 P1 — operator handoff pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "operator-handoff-pack-rg-pointers.json"


def test_operator_handoff_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 239 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_operator_handoff_claimed"] is False
    assert data["handoff_complete_claimed"] is False
    for topic in (
        "operator_handoff_stage32_h1",
        "operator_handoff_remaining_gate_stage217",
        "knowledge_base_pack_remaining_gate_stage238",
        "incident_pack_remaining_gate_stage237",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ohprp-handoff-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_operator_handoff_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OPERATOR_HANDOFF_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "OPERATOR_HANDOFF_MVP.md" in doc
    assert "OPERATOR_HANDOFF_REMAINING_GATE_MVP.md" in doc
    assert "KNOWLEDGE_BASE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_operator_handoff_claimed" in doc
