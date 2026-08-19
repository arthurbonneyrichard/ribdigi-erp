"""Stage 247 B1 — implementation onboarding pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "implementation-onboarding-pack-rg-blockers.json"


def test_implementation_onboarding_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 247 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["implementation_onboarding_program_live"] is False
    assert data["onsite_training_delivery_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_data_migration_fee_billing"] == "REMAINING"
    assert blockers["onsite_training_delivery_complete"] == "REMAINING"
    assert blockers["stage56_o1_as_live_implementation_onboarding"] == "NON_CLAIM"
    assert blockers["stage246_i1_as_live_implementation_onboarding"] == "NON_CLAIM"
    assert blockers["implementation_onboarding_program_live"] == "false"
    assert blockers["onsite_training_delivery_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ioprb-impl-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_implementation_onboarding_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/IMPLEMENTATION_ONBOARDING_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "implementation_onboarding_program_live" in doc
    assert "onsite_training_delivery_claimed" in doc
    assert "Stage 56" in doc
