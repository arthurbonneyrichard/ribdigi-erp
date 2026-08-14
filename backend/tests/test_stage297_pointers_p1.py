"""Stage 297 P1 — Commercial assurance pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-assurance-pack-rg-pointers.json"


def test_commercial_assurance_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 297 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["customer_assurance_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "commercial_assurance_stage73",
        "commercial_status_pack_remaining_gate_stage296",
        "commercial_support_pack_remaining_gate_stage295",
        "commercial_evidence_chain_stage73",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "casprp-assurance-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_assurance_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_ASSURANCE_PACK_RG_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "COMMERCIAL_ASSURANCE_MVP.md" in doc
    assert "COMMERCIAL_STATUS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_SUPPORT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_EVIDENCE_CHAIN_MVP.md" in doc
    assert "customer_assurance_claimed" in doc
    assert "evidence_chain_live_claimed" in doc
