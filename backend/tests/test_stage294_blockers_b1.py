"""Stage 294 B1 — Commercial security contact pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-security-contact-pack-rg-blockers.json"


def test_commercial_security_contact_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 294 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["security_contact_live_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["security_contact_live_claimed"] == "REMAINING"
    assert blockers["breach_drill_claimed"] == "REMAINING"
    assert blockers["vuln_disclosure_live_claimed"] == "REMAINING"
    assert blockers["commercial_support_claimed"] == "REMAINING"
    assert blockers["stage75_as_security_contact_live"] == "NON_CLAIM"
    assert blockers["security_contact_live_claimed_flag"] == "false"
    assert blockers["commercial_support_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cscprb-contact-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_security_contact_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_SECURITY_CONTACT_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "security_contact_live_claimed" in doc
    assert "breach_drill_claimed" in doc
    assert "Stage 75" in doc
