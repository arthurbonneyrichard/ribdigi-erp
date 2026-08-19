"""Stage 330 P1 — Offline materials pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-materials-pack-rg-pointers.json"


def test_offline_materials_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 330 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "offline_materials_remaining_gate_stage190",
        "offline_complete_pack_remaining_gate_stage329",
        "loadtest_baseline_pack_remaining_gate_stage328",
        "faq_offline_pos_stage171",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ofmprp-materials-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_materials_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OFFLINE_MATERIALS_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "OFFLINE_MATERIALS_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "LOADTEST_BASELINE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FAQ_OFFLINE_POS_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "browser_e2e_claimed" in doc
