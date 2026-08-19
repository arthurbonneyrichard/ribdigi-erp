"""Stage 256 P1 — commercial packaging archive pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-packaging-archive-pack-rg-pointers.json"


def test_commercial_packaging_archive_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 256 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["packaging_archive_live_claimed"] is False
    assert data["residual_closed_claimed"] is False
    for topic in (
        "commercial_packaging_archive_stage72_p1",
        "commercial_residual_pack_remaining_gate_stage255",
        "commercial_evidence_chain_pack_remaining_gate_stage254",
        "commercial_acceptance_remaining_gate_stage197",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cpaprp-archive-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_packaging_archive_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_PACKAGING_ARCHIVE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "COMMERCIAL_PACKAGING_ARCHIVE_MVP.md" in doc
    assert "COMMERCIAL_RESIDUAL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_EVIDENCE_CHAIN_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_ACCEPTANCE_REMAINING_GATE_MVP.md" in doc
    assert "packaging_archive_live_claimed" in doc
    assert "residual_closed_claimed" in doc
