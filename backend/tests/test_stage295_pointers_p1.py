"""Stage 295 P1 — Commercial support pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-support-pack-rg-pointers.json"


def test_commercial_support_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 295 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["commercial_support_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "commercial_support_stage74",
        "commercial_security_contact_pack_remaining_gate_stage294",
        "commercial_terms_pack_remaining_gate_stage293",
        "support_sla_boundary_stage36",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "csprp-support-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_support_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_SUPPORT_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "COMMERCIAL_SUPPORT_MVP.md" in doc
    assert "COMMERCIAL_SECURITY_CONTACT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_TERMS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SUPPORT_SLA_BOUNDARY_MVP.md" in doc
    assert "commercial_support_claimed" in doc
    assert "support_sla_claimed" in doc
