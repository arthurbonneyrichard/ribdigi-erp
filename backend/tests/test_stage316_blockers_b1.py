"""Stage 316 B1 — pen-test pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pentest-pack-rg-blockers.json"


def test_pentest_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 316 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["vendor_pen_test_purchased"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["vendor_pen_test_purchased"] == "REMAINING"
    assert blockers["live_zap_executed"] == "REMAINING"
    assert blockers["zap_ci_wired"] == "REMAINING"
    assert blockers["live_soak_executed"] == "REMAINING"
    assert blockers["stage29_as_vendor_pen_test"] == "NON_CLAIM"
    assert blockers["vendor_pen_test_purchased_flag"] == "false"
    assert blockers["live_zap_executed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ptprb-vendor-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pentest_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/PENTEST_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "vendor_pen_test_purchased" in doc
    assert "live_zap_executed" in doc
    assert "Stage 29" in doc
