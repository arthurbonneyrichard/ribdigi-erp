"""Stage 277 B1 — Soft-delete erasure pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "soft-delete-erasure-pack-rg-blockers.json"


def test_soft_delete_erasure_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 277 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["erasure_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["erasure_complete"] == "REMAINING"
    assert blockers["hard_delete_complete"] == "REMAINING"
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["stage37_as_erasure_complete"] == "NON_CLAIM"
    assert blockers["erasure_complete_claimed"] == "false"
    assert blockers["hard_delete_complete_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sdeprb-erasure-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_soft_delete_erasure_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SOFT_DELETE_ERASURE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "erasure_complete_claimed" in doc
    assert "hard_delete_complete_claimed" in doc
    assert "Stage 37" in doc
