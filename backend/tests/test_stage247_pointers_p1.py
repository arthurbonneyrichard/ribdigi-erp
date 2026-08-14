"""Stage 247 P1 — implementation onboarding pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "implementation-onboarding-pack-rg-pointers.json"


def test_implementation_onboarding_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 247 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["implementation_onboarding_program_live"] is False
    assert data["onsite_training_delivery_claimed"] is False
    for topic in (
        "implementation_onboarding_stage56_o1",
        "business_pilot_pack_remaining_gate_stage246",
        "professional_services_sow_pack_remaining_gate_stage243",
        "professional_services_sow_stage48",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ioprp-impl-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_implementation_onboarding_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/IMPLEMENTATION_ONBOARDING_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "IMPLEMENTATION_ONBOARDING_MVP.md" in doc
    assert "BUSINESS_PILOT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PROFESSIONAL_SERVICES_SOW_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PROFESSIONAL_SERVICES_SOW_MVP.md" in doc
    assert "implementation_onboarding_program_live" in doc
    assert "onsite_training_delivery_claimed" in doc
