"""Stage 325 P1 — golive pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "golive-pack-rg-pointers.json"


def test_golive_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 325 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["go_live_claimed"] is False
    assert data["offline_complete_claimed"] is False
    for topic in (
        "golive_remaining_gate_stage180",
        "customer_assurance_pack_remaining_gate_stage324",
        "first_tenant_live_onboarding_pack_remaining_gate_stage323",
        "first_tenant_golive_pack_remaining_gate_stage245",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "glprp-golive-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_golive_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/GOLIVE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "GOLIVE_REMAINING_GATE_MVP.md" in doc
    assert "CUSTOMER_ASSURANCE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_LIVE_ONBOARDING_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_GOLIVE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "go_live_claimed" in doc
    assert "attestation_claimed" in doc
