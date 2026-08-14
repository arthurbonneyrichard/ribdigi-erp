"""Stage 273 B1 — Store membership pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-membership-pack-rg-blockers.json"


def test_store_membership_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 273 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["store_membership_live_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["store_membership_live"] == "REMAINING"
    assert blockers["users_store_id_complete"] == "REMAINING"
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["adr005_as_store_membership_complete"] == "NON_CLAIM"
    assert blockers["store_membership_live_claimed"] == "false"
    assert blockers["users_store_id_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "smprb-membership-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_membership_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/STORE_MEMBERSHIP_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "store_membership_live_claimed" in doc
    assert "users_store_id_claimed" in doc
    assert "ADR-005" in doc or "ADR_005" in doc
