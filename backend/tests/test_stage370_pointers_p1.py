"""Stage 370 P1 — permission alias pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "permission-alias-pack-rg-pointers.json"


def test_permission_alias_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 370 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["permission_rename_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "change_impact_p2_permission_aliases",
        "sync_conflict_ux_pack_remaining_gate_stage369",
        "adr_004_menu_permissions",
        "menu_permissions_pack_remaining_gate_stage275",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "paprgp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_permission_alias_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PERMISSION_ALIAS_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md" in doc
    assert "SYNC_CONFLICT_UX_PACK_REMAINING_GATE_MVP.md" in doc
    assert "ADR_004_MENU_PERMISSIONS.md" in doc
    assert "MENU_PERMISSIONS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "permission_rename_complete_claimed" in doc
    assert "products_stock_alias_map_complete_claimed" in doc
