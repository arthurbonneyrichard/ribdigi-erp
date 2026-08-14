"""Stage 323 I1 — first-tenant live onboarding pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-live-onboarding-pack-remaining-gate.json"


def test_first_tenant_live_onboarding_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 323 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["first_tenant_onboarded_claimed"] is False
    assert data["live_onboarding_success_claimed"] is False
    assert data["first_paying_tenant_claimed"] is False
    assert data["demo_tenant_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage194_first_tenant_live_onboarding_remaining_gate"] is True
    assert data["distinct_from_first_tenant_onboarding_pack"] is True
    assert data["distinct_from_first_tenant_golive_pack"] is True
    assert data["distinct_from_stage322_live_migration_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ftlopr-onboarding-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_live_onboarding_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/FIRST_TENANT_LIVE_ONBOARDING_PACK_REMAINING_GATE_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "first_tenant_onboarded_claimed" in doc
    assert "live_onboarding_success_claimed" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 194" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_REMAINING_GATE_MVP.md" in doc
    assert "CUSTOMER_ASSURANCE_REMAINING_GATE_MVP.md" in doc
