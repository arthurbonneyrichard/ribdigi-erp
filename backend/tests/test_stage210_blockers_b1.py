"""Stage 210 B1 — security scan blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "security-scan-blockers.json"


def test_security_scan_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 210 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_security_scan_claimed"] is False
    assert data["live_zap_executed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_security_scan_authenticated_staging_zap"] == "REMAINING"
    assert blockers["zap_wired_into_main_ci"] == "NON_CLAIM"
    assert blockers["stage27_s1_as_live_security_scan"] == "NON_CLAIM"
    assert blockers["live_security_scan_claimed"] == "false"
    assert blockers["live_zap_executed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sb-scan-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_security_scan_blockers_doc_b1():
    doc = (ROOT / "docs/SECURITY_SCAN_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_security_scan_claimed" in doc
    assert "Stage 27" in doc
    assert "live_zap_executed" in doc
