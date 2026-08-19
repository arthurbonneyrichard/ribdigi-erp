"""Stage 390 B1 — offline catalog snapshot pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-catalog-snapshot-pack-rg-blockers.json"


def test_offline_catalog_snapshot_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 390 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["offline_complete_claimed"] == "REMAINING"
    assert blockers["offline_catalog_snapshot_complete_claimed"] == "REMAINING"
    assert blockers["catalog_snapshot_cache_complete_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["attestation_claimed"] == "REMAINING"
    assert blockers["stage377_as_offline_catalog_snapshot"] == "NON_CLAIM"
    assert blockers["offline_complete_claimed_flag"] == "false"
    assert blockers["go_live_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ocsprb-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_catalog_snapshot_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/OFFLINE_CATALOG_SNAPSHOT_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "offline_catalog_snapshot_complete_claimed" in doc
    assert "Stage 377" in doc
