"""Stage 315 I1 — security scan pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "security-scan-pack-remaining-gate.json"


def test_security_scan_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 315 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_security_scan_claimed"] is False
    assert data["live_zap_executed"] is False
    assert data["vendor_pen_test_purchased"] is False
    assert data["zap_ci_wired"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage27_security_scan"] is True
    assert data["distinct_from_stage210_security_scan_remaining_gate"] is True
    assert data["distinct_from_stage314_sbom_disclosure_pack_remaining_gate"] is True
    assert data["distinct_from_stage313_commercial_liability_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sscpr-scan-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_security_scan_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/SECURITY_SCAN_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_security_scan_claimed" in doc
    assert "live_zap_executed" in doc
    assert "SECURITY_SCAN_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "SECURITY_SCAN_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 27" in doc
    assert "SECURITY_SCAN_MVP.md" in doc
    assert "SECURITY_SCAN_REMAINING_GATE_MVP.md" in doc
