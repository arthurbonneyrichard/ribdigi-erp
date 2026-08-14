"""Stage 378 P1 — offline hold soft-reserve pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-hold-reserve-pack-rg-pointers.json"


def test_offline_hold_reserve_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 378 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "change_impact_section22_offline_hold_reserve",
        "offline_catalog_ttl_pack_remaining_gate_stage377",
        "stage166_hold_soft_reserve_fidelity",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ohsrprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_hold_reserve_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OFFLINE_HOLD_RESERVE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md" in doc
    assert "OFFLINE_CATALOG_TTL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STAGE_166_FIDELITY.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "offline_hold_reserve_complete_claimed" in doc
