"""Stage 275 P1 — Menu permissions pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "menu-permissions-pack-rg-pointers.json"


def test_menu_permissions_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 275 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["dynamic_menu_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "menu_permissions_adr004",
        "language_i18n_pack_remaining_gate_stage274",
        "store_membership_pack_remaining_gate_stage273",
        "deferred_adr_register_stage31",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "mpprp-dynamic-menu-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_menu_permissions_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/MENU_PERMISSIONS_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_004_MENU_PERMISSIONS.md" in doc
    assert "LANGUAGE_I18N_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STORE_MEMBERSHIP_PACK_REMAINING_GATE_MVP.md" in doc
    assert "DEFERRED_ADR_REGISTER_MVP.md" in doc
    assert "dynamic_menu_complete_claimed" in doc
    assert "submenu_flags_claimed" in doc
