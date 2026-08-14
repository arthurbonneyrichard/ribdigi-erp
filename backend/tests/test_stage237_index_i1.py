"""Stage 237 I1 — incident pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "incident-pack-remaining-gate.json"


def test_incident_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 237 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_incident_drill_claimed"] is False
    assert data["live_incident_response_claimed"] is False
    assert data["hosted_pagerduty_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage30_i1_incident_pack"] is True
    assert data["distinct_from_stage211_incident_remaining_gate"] is True
    assert data["distinct_from_stage236_support_runbook_pack_remaining_gate"] is True
    assert data["distinct_from_stage235_evidence_ledger_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ipr-drill-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_incident_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/INCIDENT_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_incident_drill_claimed" in doc
    assert "INCIDENT_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "INCIDENT_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 30" in doc
    assert "Stage 211" in doc
