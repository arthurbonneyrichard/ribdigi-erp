"""Stage 334 B1 — incident severity pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "incident-severity-pack-rg-blockers.json"


def test_incident_severity_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 334 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["pagerduty_hosted_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["pagerduty_hosted_claimed"] == "REMAINING"
    assert blockers["oncall_rota_live"] == "REMAINING"
    assert blockers["incident_drill_executed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["attestation_claimed"] == "REMAINING"
    assert blockers["stage170_as_live_incident_severity"] == "NON_CLAIM"
    assert blockers["pagerduty_hosted_claimed_flag"] == "false"
    assert blockers["incident_drill_executed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "isprb-severity-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_incident_severity_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/INCIDENT_SEVERITY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "pagerduty_hosted_claimed" in doc
    assert "incident_drill_executed" in doc
    assert "Stage 170" in doc
