"""Stage 246 P1 — business pilot pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "business-pilot-pack-rg-pointers.json"


def test_business_pilot_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 246 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["controlled_business_pilot_live_claimed"] is False
    assert data["business_pilot_program_live"] is False
    for topic in (
        "business_pilot_stage65_p1",
        "first_tenant_golive_pack_remaining_gate_stage245",
        "first_tenant_onboarding_pack_remaining_gate_stage244",
        "implementation_onboarding_stage56",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "bpprp-pilot-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_business_pilot_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/BUSINESS_PILOT_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "BUSINESS_PILOT_MVP.md" in doc
    assert "FIRST_TENANT_GOLIVE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_ONBOARDING_PACK_REMAINING_GATE_MVP.md" in doc
    assert "IMPLEMENTATION_ONBOARDING_MVP.md" in doc
    assert "controlled_business_pilot_live_claimed" in doc
    assert "business_pilot_program_live" in doc
