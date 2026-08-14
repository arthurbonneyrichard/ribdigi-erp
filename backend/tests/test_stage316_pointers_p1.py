"""Stage 316 P1 — pen-test pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pentest-pack-rg-pointers.json"


def test_pentest_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 316 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["vendor_pen_test_purchased"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "pentest_pack_stage29",
        "security_scan_pack_remaining_gate_stage315",
        "sbom_disclosure_pack_remaining_gate_stage314",
        "pentest_remaining_gate_stage209",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ptprp-vendor-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pentest_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PENTEST_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PENTEST_PACK_MVP.md" in doc
    assert "SECURITY_SCAN_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SBOM_DISCLOSURE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PENTEST_REMAINING_GATE_MVP.md" in doc
    assert "vendor_pen_test_purchased" in doc
    assert "live_zap_executed" in doc
