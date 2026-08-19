"""Stage 210 P1 — security scan pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "security-scan-pack-pointers.json"


def test_security_scan_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 210 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_security_scan_claimed"] is False
    assert data["live_zap_executed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "security_scan_stage27",
        "zap_baseline_template",
        "security_ops_notes",
        "pentest_remaining_gate_stage209",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sp-scan-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_security_scan_pack_pointers_doc_p1():
    doc = (ROOT / "docs/SECURITY_SCAN_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SECURITY_SCAN_MVP.md" in doc
    assert "PENTEST_REMAINING_GATE_MVP.md" in doc
    assert "zap-baseline" in doc
    assert "live_security_scan_claimed" in doc
