"""Stage 324 P1 — customer assurance pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "customer-assurance-pack-rg-pointers.json"


def test_customer_assurance_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 324 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["customer_assurance_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "customer_assurance_remaining_gate_stage195",
        "first_tenant_live_onboarding_pack_remaining_gate_stage323",
        "live_migration_pack_remaining_gate_stage322",
        "residual_risk_remaining_gate_stage196",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "casprp-assurance-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_customer_assurance_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/CUSTOMER_ASSURANCE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CUSTOMER_ASSURANCE_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_PACK_REMAINING_GATE_MVP.md" in doc
    assert "LIVE_MIGRATION_PACK_REMAINING_GATE_MVP.md" in doc
    assert "RESIDUAL_RISK_REMAINING_GATE_MVP.md" in doc
    assert "customer_assurance_claimed" in doc
    assert "evidence_chain_live_claimed" in doc
