"""Stage 378 B1 — offline hold soft-reserve pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-hold-reserve-pack-rg-blockers.json"


def test_offline_hold_reserve_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 378 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["offline_complete_claimed"] == "REMAINING"
    assert blockers["offline_hold_reserve_complete_claimed"] == "REMAINING"
    assert blockers["reserved_qty_complete_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["attestation_claimed"] == "REMAINING"
    assert blockers["stage166_as_offline_hold_reserve"] == "NON_CLAIM"
    assert blockers["offline_complete_claimed_flag"] == "false"
    assert blockers["go_live_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ohsrprb-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_hold_reserve_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/OFFLINE_HOLD_RESERVE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "offline_hold_reserve_complete_claimed" in doc
    assert "Stage 166" in doc
