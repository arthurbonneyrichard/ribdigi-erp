"""Stage 194 P1 — first-tenant live onboarding pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-live-onboarding-pack-pointers.json"


def test_first_tenant_live_onboarding_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 194 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["first_tenant_onboarded_claimed"] is False
    assert data["live_onboarding_success_claimed"] is False
    assert data["demo_tenant_claimed"] is False
    for topic in (
        "first_tenant_onboarding_stage33",
        "first_tenant_golive_stage66",
        "live_migration_remaining_gate_stage193",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "fp-onboarding-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_live_onboarding_pack_pointers_doc_p1():
    doc = (ROOT / "docs/FIRST_TENANT_LIVE_ONBOARDING_PACK_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "FIRST_TENANT_ONBOARDING_MVP.md" in doc
    assert "FIRST_TENANT_GOLIVE_MVP.md" in doc
    assert "LIVE_MIGRATION_REMAINING_GATE_MVP.md" in doc
    assert "live_onboarding_success_claimed" in doc
