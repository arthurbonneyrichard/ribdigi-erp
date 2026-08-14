"""Stage 260 B1 — commercial go-live closeout pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-golive-closeout-pack-rg-blockers.json"


def test_commercial_golive_closeout_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 260 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["commercial_golive_closeout_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["commercial_golive_closeout_complete"] == "REMAINING"
    assert blockers["first_commercial_day_complete"] == "REMAINING"
    assert blockers["go_live_complete"] == "REMAINING"
    assert blockers["stage70_g1_as_closeout_live"] == "NON_CLAIM"
    assert blockers["commercial_golive_closeout_claimed"] == "false"
    assert blockers["go_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cgcprb-closeout-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_golive_closeout_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_GOLIVE_CLOSEOUT_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "commercial_golive_closeout_claimed" in doc
    assert "go_live_claimed" in doc
    assert "Stage 70" in doc
