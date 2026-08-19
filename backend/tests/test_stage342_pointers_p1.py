"""Stage 342 P1 — shift handover checklist pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "shift-handover-checklist-pack-rg-pointers.json"


def test_shift_handover_checklist_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 342 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "shift_handover_checklist_stage175",
        "store_close_checklist_pack_remaining_gate_stage341",
        "store_open_checklist_pack_remaining_gate_stage340",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "shcprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_shift_handover_checklist_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SHIFT_HANDOVER_CHECKLIST_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SHIFT_HANDOVER_CHECKLIST_MVP.md" in doc
    assert "STORE_CLOSE_CHECKLIST_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STORE_OPEN_CHECKLIST_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "live_dr_claimed" in doc
