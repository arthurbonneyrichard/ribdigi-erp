"""Stage 346 P1 — monthly POS ops review pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "monthly-pos-ops-review-pack-rg-pointers.json"


def test_monthly_pos_ops_review_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 346 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "monthly_pos_ops_review_stage177",
        "weekly_pos_ops_signals_pack_remaining_gate_stage345",
        "weekly_pos_ops_review_pack_remaining_gate_stage344",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "mporprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_monthly_pos_ops_review_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/MONTHLY_POS_OPS_REVIEW_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "MONTHLY_POS_OPS_REVIEW_MVP.md" in doc
    assert "WEEKLY_POS_OPS_SIGNALS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "WEEKLY_POS_OPS_REVIEW_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "live_dr_claimed" in doc
