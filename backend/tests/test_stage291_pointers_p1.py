"""Stage 291 P1 — Commercial privacy notice pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-privacy-notice-pack-rg-pointers.json"


def test_commercial_privacy_notice_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 291 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["privacy_notice_live"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "commercial_privacy_notice_stage75",
        "cookie_privacy_notice_pack_remaining_gate_stage290",
        "change_governance_pack_remaining_gate_stage289",
        "commercial_security_contact_stage75",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cpnprp-notice-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_privacy_notice_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_PRIVACY_NOTICE_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "COMMERCIAL_PRIVACY_NOTICE_MVP.md" in doc
    assert "COOKIE_PRIVACY_NOTICE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "CHANGE_GOVERNANCE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_SECURITY_CONTACT_MVP.md" in doc
    assert "privacy_notice_live" in doc or "privacy notice live" in doc.lower()
    assert "cookie_consent_live" in doc or "cookie consent" in doc.lower()
