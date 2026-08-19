"""Stage 211 P1 — incident pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "incident-pack-pointers.json"


def test_incident_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 211 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_incident_response_claimed"] is False
    assert data["oncall_rota_live"] is False
    assert data["incident_drill_executed"] is False
    assert data["pagerduty_hosted_claimed"] is False
    for topic in (
        "incident_pack_stage30",
        "incident_checklist",
        "oncall_runbook_example",
        "severity_matrix",
        "security_scan_remaining_gate_stage210",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ip-incident-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_incident_pack_pointers_doc_p1():
    doc = (ROOT / "docs/INCIDENT_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "INCIDENT_PACK_MVP.md" in doc
    assert "SECURITY_SCAN_REMAINING_GATE_MVP.md" in doc
    assert "incident-checklist" in doc
    assert "live_incident_response_claimed" in doc
