"""Stage 315 B1 — security scan pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "security-scan-pack-rg-blockers.json"


def test_security_scan_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 315 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_security_scan_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_security_scan_claimed"] == "REMAINING"
    assert blockers["live_zap_executed"] == "REMAINING"
    assert blockers["vendor_pen_test_purchased"] == "REMAINING"
    assert blockers["zap_ci_wired"] == "REMAINING"
    assert blockers["stage27_as_live_security_scan"] == "NON_CLAIM"
    assert blockers["live_security_scan_claimed_flag"] == "false"
    assert blockers["live_zap_executed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sscprb-scan-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_security_scan_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SECURITY_SCAN_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_security_scan_claimed" in doc
    assert "live_zap_executed" in doc
    assert "Stage 27" in doc
