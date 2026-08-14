"""Stage 247 I1 — implementation onboarding pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "implementation-onboarding-pack-remaining-gate.json"


def test_implementation_onboarding_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 247 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["data_migration_fee_billing_live"] is False
    assert data["onsite_training_delivery_claimed"] is False
    assert data["custom_workflow_sold_claimed"] is False
    assert data["implementation_onboarding_program_live"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage56_o1_implementation_onboarding"] is True
    assert data["distinct_from_stage246_business_pilot_pack_remaining_gate"] is True
    assert data["distinct_from_stage243_professional_services_sow_pack_remaining_gate"] is True
    assert data["distinct_from_stage48_professional_services_sow"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "iopr-impl-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_implementation_onboarding_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/IMPLEMENTATION_ONBOARDING_PACK_REMAINING_GATE_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "implementation_onboarding_program_live" in doc
    assert "onsite_training_delivery_claimed" in doc
    assert "IMPLEMENTATION_ONBOARDING_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "IMPLEMENTATION_ONBOARDING_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 56" in doc
    assert "Stage 246" in doc
