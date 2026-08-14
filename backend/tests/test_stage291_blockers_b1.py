"""Stage 291 B1 — Commercial privacy notice pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-privacy-notice-pack-rg-blockers.json"


def test_commercial_privacy_notice_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 291 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["privacy_notice_live"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["privacy_notice_live"] == "REMAINING"
    assert blockers["cookie_consent_live"] == "REMAINING"
    assert blockers["security_contact_live"] == "REMAINING"
    assert blockers["commercial_support"] == "REMAINING"
    assert blockers["stage75_as_privacy_notice_live"] == "NON_CLAIM"
    assert blockers["privacy_notice_live_claimed"] == "false"
    assert blockers["cookie_consent_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cpnprb-notice-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_privacy_notice_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_PRIVACY_NOTICE_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "privacy_notice_live" in doc or "privacy notice live" in doc.lower()
    assert "cookie_consent_live" in doc or "cookie consent" in doc.lower()
    assert "Stage 75" in doc
