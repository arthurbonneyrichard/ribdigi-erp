"""Stage 287 P1 — Vuln disclosure pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "vuln-disclosure-pack-rg-pointers.json"


def test_vuln_disclosure_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 287 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["disclosure_program_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "vuln_disclosure_stage38",
        "breach_notification_pack_remaining_gate_stage286",
        "incident_pack_remaining_gate_stage211",
        "security_scan_stage27",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "vdprp-program-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_vuln_disclosure_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/VULN_DISCLOSURE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "VULN_DISCLOSURE_MVP.md" in doc
    assert "BREACH_NOTIFICATION_PACK_REMAINING_GATE_MVP.md" in doc
    assert "INCIDENT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SECURITY_SCAN_MVP.md" in doc
    assert "disclosure_program_claimed" in doc
    assert "bug_bounty_claimed" in doc
