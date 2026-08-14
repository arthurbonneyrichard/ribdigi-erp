"""Stage 287 B1 — Vuln disclosure pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "vuln-disclosure-pack-rg-blockers.json"


def test_vuln_disclosure_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 287 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["disclosure_program_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["disclosure_program"] == "REMAINING"
    assert blockers["bug_bounty"] == "REMAINING"
    assert blockers["continuous_disclosure"] == "REMAINING"
    assert blockers["researcher_intake_live"] == "REMAINING"
    assert blockers["stage38_as_disclosure_program"] == "NON_CLAIM"
    assert blockers["disclosure_program_claimed"] == "false"
    assert blockers["bug_bounty_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "vdprb-program-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_vuln_disclosure_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/VULN_DISCLOSURE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "disclosure_program_claimed" in doc
    assert "bug_bounty_claimed" in doc
    assert "Stage 38" in doc
