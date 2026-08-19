"""Stage 340 P1 — store open checklist pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-open-checklist-pack-rg-pointers.json"


def test_store_open_checklist_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 340 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "store_open_checklist_stage173",
        "cashier_quickstart_pack_remaining_gate_stage339",
        "troubleshooting_index_pack_remaining_gate_stage338",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "socprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_open_checklist_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/STORE_OPEN_CHECKLIST_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "STORE_OPEN_CHECKLIST_MVP.md" in doc
    assert "CASHIER_QUICKSTART_PACK_REMAINING_GATE_MVP.md" in doc
    assert "TROUBLESHOOTING_INDEX_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "live_training_claimed" in doc
