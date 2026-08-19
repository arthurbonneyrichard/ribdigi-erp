"""Stage 332 P1 — support SLA pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-sla-pack-rg-pointers.json"


def test_support_sla_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 332 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["support_sla_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "support_sla_remaining_gate_stage188",
        "support_sla_boundary_pack_remaining_gate_stage331",
        "offline_materials_pack_remaining_gate_stage330",
        "support_sla_boundary_stage36",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ssprp-sla-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_support_sla_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SUPPORT_SLA_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SUPPORT_SLA_REMAINING_GATE_MVP.md" in doc
    assert "SUPPORT_SLA_BOUNDARY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_MATERIALS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SUPPORT_SLA_BOUNDARY_MVP.md" in doc
    assert "support_sla_claimed" in doc
    assert "pagerduty_hosted_claimed" in doc
