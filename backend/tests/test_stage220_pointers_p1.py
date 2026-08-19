"""Stage 220 P1 — support SLA boundary RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-sla-boundary-rg-pointers.json"


def test_support_sla_boundary_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 220 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_support_sla_boundary_claimed"] is False
    assert data["support_sla_claimed"] is False
    for topic in (
        "support_sla_boundary_stage36_s1",
        "support_runbook_stage30",
        "production_hypercare_remaining_gate_stage219",
        "support_sla_remaining_gate_stage188",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ssbp-sla-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_support_sla_boundary_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SUPPORT_SLA_BOUNDARY_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SUPPORT_SLA_BOUNDARY_MVP.md" in doc
    assert "PRODUCTION_HYPERCARE_REMAINING_GATE_MVP.md" in doc
    assert "SUPPORT_SLA_REMAINING_GATE_MVP.md" in doc
    assert "live_support_sla_boundary_claimed" in doc
