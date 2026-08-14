"""Stage 235 P1 — evidence ledger pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "evidence-ledger-pack-rg-pointers.json"


def test_evidence_ledger_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 235 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_go_live_evidence_claimed"] is False
    assert data["live_evidence_ledger_claimed"] is False
    for topic in (
        "evidence_ledger_stage30_l1",
        "evidence_ledger_remaining_gate_stage212",
        "load_capacity_pack_remaining_gate_stage234",
        "wal_offsite_remaining_gate_stage233",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "elprp-evidence-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_evidence_ledger_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/EVIDENCE_LEDGER_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "EVIDENCE_LEDGER_MVP.md" in doc
    assert "EVIDENCE_LEDGER_REMAINING_GATE_MVP.md" in doc
    assert "LOAD_CAPACITY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_go_live_evidence_claimed" in doc
