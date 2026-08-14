"""Stage 356 B1 — store open lowstock pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-open-lowstock-pack-rg-blockers.json"


def test_store_open_lowstock_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 356 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["offline_complete_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["attestation_claimed"] == "REMAINING"
    assert blockers["auto_po_claimed"] == "REMAINING"
    assert blockers["offline_stock_authoritative_claimed"] == "REMAINING"
    assert blockers["stage173_as_live_store_open_lowstock"] == "NON_CLAIM"
    assert blockers["offline_complete_claimed_flag"] == "false"
    assert blockers["auto_po_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "solprb-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_open_lowstock_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/STORE_OPEN_LOWSTOCK_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "auto_po_claimed" in doc
    assert "Stage 173" in doc
