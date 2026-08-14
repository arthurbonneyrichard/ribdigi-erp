"""Stage 244 P1 — first-tenant onboarding pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-onboarding-pack-rg-pointers.json"


def test_first_tenant_onboarding_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 244 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["first_tenant_onboarded_claimed"] is False
    assert data["live_onboarding_success_claimed"] is False
    assert data["first_paying_tenant_claimed"] is False
    for topic in (
        "first_tenant_onboarding_stage33_f1",
        "professional_services_sow_pack_remaining_gate_stage243",
        "first_tenant_live_onboarding_remaining_gate_stage194",
        "first_tenant_golive_stage66",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ftoprp-onboarding-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_onboarding_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/FIRST_TENANT_ONBOARDING_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "FIRST_TENANT_ONBOARDING_MVP.md" in doc
    assert "PROFESSIONAL_SERVICES_SOW_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_GOLIVE_MVP.md" in doc
    assert "first_tenant_onboarded_claimed" in doc
    assert "live_onboarding_success_claimed" in doc
