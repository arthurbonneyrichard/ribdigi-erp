"""Stage 237 B1 — incident pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "incident-pack-rg-blockers.json"


def test_incident_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 237 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_incident_drill_claimed"] is False
    assert data["live_incident_response_claimed"] is False
    assert data["hosted_pagerduty_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_incident_oncall_drill_execution"] == "REMAINING"
    assert blockers["hosted_pagerduty_live_paging"] == "REMAINING"
    assert blockers["stage30_i1_as_live_incident_drill"] == "NON_CLAIM"
    assert blockers["live_incident_drill_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "iprb-drill-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_incident_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/INCIDENT_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_incident_drill_claimed" in doc
    assert "Stage 30" in doc
