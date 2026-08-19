"""Stage 370 B1 — permission alias pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "permission-alias-pack-rg-blockers.json"


def test_permission_alias_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 370 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["permission_rename_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["permission_rename_complete_claimed"] == "REMAINING"
    assert blockers["products_stock_alias_map_complete_claimed"] == "REMAINING"
    assert blockers["offline_complete_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["attestation_claimed"] == "REMAINING"
    assert blockers["adr004_as_rename_complete"] == "NON_CLAIM"
    assert blockers["permission_rename_complete_claimed_flag"] == "false"
    assert blockers["go_live_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "paprgb-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_permission_alias_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/PERMISSION_ALIAS_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "permission_rename_complete_claimed" in doc
    assert "products_stock_alias_map_complete_claimed" in doc
    assert "ADR-004" in doc
