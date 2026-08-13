"""Stage 190 P1 — offline materials pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-materials-pack-pointers.json"


def test_offline_materials_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 190 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["browser_e2e_claimed"] is False
    for topic in (
        "faq_offline_pos_stage171",
        "cashier_quickstart_stage172",
        "store_checklists_stages173_175",
        "offline_complete_remaining_gate_stage179",
        "live_training_remaining_gate_stage189",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "op-offline-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_materials_pack_pointers_doc_p1():
    doc = (ROOT / "docs/OFFLINE_MATERIALS_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "FAQ_OFFLINE_POS_MVP.md" in doc
    assert "CASHIER_QUICKSTART_MVP.md" in doc
    assert "OFFLINE_COMPLETE_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
