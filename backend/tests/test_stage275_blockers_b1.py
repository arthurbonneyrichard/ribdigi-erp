"""Stage 275 B1 — Menu permissions pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "menu-permissions-pack-rg-blockers.json"


def test_menu_permissions_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 275 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["dynamic_menu_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["dynamic_menu_complete"] == "REMAINING"
    assert blockers["submenu_flags_complete"] == "REMAINING"
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["adr004_as_dynamic_menu_complete"] == "NON_CLAIM"
    assert blockers["dynamic_menu_complete_claimed"] == "false"
    assert blockers["submenu_flags_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "mpprb-dynamic-menu-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_menu_permissions_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/MENU_PERMISSIONS_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "dynamic_menu_complete_claimed" in doc
    assert "submenu_flags_claimed" in doc
    assert "ADR-004" in doc or "ADR_004" in doc
