"""Stage 289 P1 — Change governance pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "change-governance-pack-rg-pointers.json"


def test_change_governance_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 289 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["change_calendar_live"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "change_governance_stage41",
        "cyber_insurance_pack_remaining_gate_stage288",
        "accessibility_statement_pack_remaining_gate_stage285",
        "cutover_pack_stage29",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cgprp-calendar-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_change_governance_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/CHANGE_GOVERNANCE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CHANGE_GOVERNANCE_MVP.md" in doc
    assert "CYBER_INSURANCE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "ACCESSIBILITY_STATEMENT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "CUTOVER_PACK_MVP.md" in doc
    assert "change_calendar_live" in doc
    assert "maintenance_portal_claimed" in doc
