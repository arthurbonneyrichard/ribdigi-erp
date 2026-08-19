"""Stage 276 B1 — Hard delete pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "hard-delete-pack-rg-blockers.json"


def test_hard_delete_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 276 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["hard_delete_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["hard_delete_complete"] == "REMAINING"
    assert blockers["archival_complete"] == "REMAINING"
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["adr003_as_hard_delete_complete"] == "NON_CLAIM"
    assert blockers["hard_delete_complete_claimed"] == "false"
    assert blockers["archival_complete_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "hdprb-hard-delete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_hard_delete_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/HARD_DELETE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "hard_delete_complete_claimed" in doc
    assert "archival_complete_claimed" in doc
    assert "ADR-003" in doc or "ADR_003" in doc
