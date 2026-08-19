"""Stage 338 P1 — troubleshooting index pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "troubleshooting-index-pack-rg-pointers.json"


def test_troubleshooting_index_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 338 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["support_sla_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "troubleshooting_index_stage171",
        "faq_offline_pos_pack_remaining_gate_stage337",
        "offline_sync_runbook_pack_remaining_gate_stage336",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tiprp-index-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_troubleshooting_index_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/TROUBLESHOOTING_INDEX_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "TROUBLESHOOTING_INDEX_MVP.md" in doc
    assert "FAQ_OFFLINE_POS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_SYNC_RUNBOOK_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "support_sla_claimed" in doc
    assert "offline_complete_claimed" in doc
