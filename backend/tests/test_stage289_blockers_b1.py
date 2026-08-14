"""Stage 289 B1 — Change governance pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "change-governance-pack-rg-blockers.json"


def test_change_governance_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 289 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["change_calendar_live"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["change_calendar_live"] == "REMAINING"
    assert blockers["maintenance_portal"] == "REMAINING"
    assert blockers["customer_change_notices_live"] == "REMAINING"
    assert blockers["ops_changelog_saas"] == "REMAINING"
    assert blockers["stage41_as_change_calendar"] == "NON_CLAIM"
    assert blockers["maintenance_portal_claimed"] == "false"
    assert blockers["ops_changelog_saas_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cgprb-calendar-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_change_governance_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/CHANGE_GOVERNANCE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "change_calendar_live" in doc
    assert "maintenance_portal_claimed" in doc
    assert "Stage 41" in doc
