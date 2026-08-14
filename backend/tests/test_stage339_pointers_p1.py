"""Stage 339 P1 — cashier quickstart pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cashier-quickstart-pack-rg-pointers.json"


def test_cashier_quickstart_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 339 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "cashier_quickstart_stage172",
        "troubleshooting_index_pack_remaining_gate_stage338",
        "faq_offline_pos_pack_remaining_gate_stage337",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cqprp-quickstart-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cashier_quickstart_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/CASHIER_QUICKSTART_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CASHIER_QUICKSTART_MVP.md" in doc
    assert "TROUBLESHOOTING_INDEX_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FAQ_OFFLINE_POS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "live_training_claimed" in doc
