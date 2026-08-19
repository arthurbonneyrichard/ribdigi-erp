"""Stage 236 P1 — support runbook pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-runbook-pack-rg-pointers.json"


def test_support_runbook_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 236 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_support_sla_claimed"] is False
    assert data["live_support_runbook_claimed"] is False
    for topic in (
        "support_runbook_stage30_s1",
        "support_runbook_remaining_gate_stage214",
        "support_sla_remaining_gate_stage188",
        "evidence_ledger_pack_remaining_gate_stage235",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "srprp-sla-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_support_runbook_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SUPPORT_RUNBOOK_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SUPPORT_RUNBOOK_MVP.md" in doc
    assert "SUPPORT_RUNBOOK_REMAINING_GATE_MVP.md" in doc
    assert "EVIDENCE_LEDGER_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_support_sla_claimed" in doc
