"""Stage 328 B1 — loadtest baseline pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "loadtest-baseline-pack-rg-blockers.json"


def test_loadtest_baseline_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 328 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["certified_load_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["certified_load_claimed"] == "REMAINING"
    assert blockers["live_load_capacity_claimed"] == "REMAINING"
    assert blockers["operator_1000vu_executed"] == "REMAINING"
    assert blockers["load_cert_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["stage225_as_live_certified_load"] == "NON_CLAIM"
    assert blockers["certified_load_claimed_flag"] == "false"
    assert blockers["live_load_capacity_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ltbprb-load-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_loadtest_baseline_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LOADTEST_BASELINE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "certified_load_claimed" in doc
    assert "live_load_capacity_claimed" in doc
    assert "Stage 225" in doc
