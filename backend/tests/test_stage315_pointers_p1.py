"""Stage 315 P1 — security scan pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "security-scan-pack-rg-pointers.json"


def test_security_scan_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 315 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_security_scan_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "security_scan_stage27",
        "sbom_disclosure_pack_remaining_gate_stage314",
        "commercial_liability_pack_remaining_gate_stage313",
        "security_scan_remaining_gate_stage210",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sscprp-scan-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_security_scan_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SECURITY_SCAN_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SECURITY_SCAN_MVP.md" in doc
    assert "SBOM_DISCLOSURE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_LIABILITY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SECURITY_SCAN_REMAINING_GATE_MVP.md" in doc
    assert "live_security_scan_claimed" in doc
    assert "live_zap_executed" in doc
