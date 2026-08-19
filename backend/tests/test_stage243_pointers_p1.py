"""Stage 243 P1 — professional services SOW pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "professional-services-sow-pack-rg-pointers.json"


def test_professional_services_sow_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 243 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["signed_sow_claimed"] is False
    assert data["implementation_delivery_claimed"] is False
    assert data["professional_services_live_claimed"] is False
    for topic in (
        "professional_services_sow_stage48_p1",
        "customer_training_cert_pack_remaining_gate_stage242",
        "first_tenant_onboarding_stage33",
        "commercial_professional_services_stage78",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pssprp-sow-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_professional_services_sow_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PROFESSIONAL_SERVICES_SOW_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "PROFESSIONAL_SERVICES_SOW_MVP.md" in doc
    assert "CUSTOMER_TRAINING_CERT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_TENANT_ONBOARDING_MVP.md" in doc
    assert "COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md" in doc
    assert "signed_sow_claimed" in doc
    assert "implementation_delivery_claimed" in doc
