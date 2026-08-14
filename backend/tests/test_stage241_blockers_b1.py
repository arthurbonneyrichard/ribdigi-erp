"""Stage 241 B1 — live training pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-training-pack-rg-blockers.json"


def test_live_training_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 241 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_training_claimed"] is False
    assert data["training_complete_claimed"] is False
    assert data["training_certification_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_training_delivery_execution"] == "REMAINING"
    assert blockers["training_certification_complete"] == "REMAINING"
    assert blockers["stage189_i1_as_live_training"] == "NON_CLAIM"
    assert blockers["stage48_t1_as_live_training"] == "NON_CLAIM"
    assert blockers["live_training_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ltprb-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_training_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LIVE_TRAINING_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_training_claimed" in doc
    assert "Stage 189" in doc
