"""Stage 294 P1 — Commercial security contact pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-security-contact-pack-rg-pointers.json"


def test_commercial_security_contact_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 294 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["security_contact_live_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "commercial_security_contact_stage75",
        "commercial_terms_pack_remaining_gate_stage293",
        "commercial_dpa_pack_remaining_gate_stage292",
        "breach_notification_stage38",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cscprp-contact-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_security_contact_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_SECURITY_CONTACT_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "COMMERCIAL_SECURITY_CONTACT_MVP.md" in doc
    assert "COMMERCIAL_TERMS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_DPA_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BREACH_NOTIFICATION_MVP.md" in doc
    assert "security_contact_live_claimed" in doc
    assert "commercial_support_claimed" in doc
