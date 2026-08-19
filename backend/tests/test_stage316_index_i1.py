"""Stage 316 I1 — pen-test pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pentest-pack-remaining-gate.json"


def test_pentest_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 316 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["vendor_pen_test_purchased"] is False
    assert data["live_zap_executed"] is False
    assert data["zap_ci_wired"] is False
    assert data["live_soak_executed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage29_pentest_pack"] is True
    assert data["distinct_from_stage209_pentest_remaining_gate"] is True
    assert data["distinct_from_stage315_security_scan_pack_remaining_gate"] is True
    assert data["distinct_from_stage314_sbom_disclosure_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ptpr-vendor-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pentest_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/PENTEST_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "vendor_pen_test_purchased" in doc
    assert "live_zap_executed" in doc
    assert "PENTEST_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "PENTEST_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 29" in doc
    assert "PENTEST_PACK_MVP.md" in doc
    assert "PENTEST_REMAINING_GATE_MVP.md" in doc
