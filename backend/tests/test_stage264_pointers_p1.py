"""Stage 264 P1 — production hypercare pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "production-hypercare-pack-rg-pointers.json"


def test_production_hypercare_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 264 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["production_hypercare_live_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "production_hypercare_stage67_h1",
        "golive_attestation_pack_remaining_gate_stage263",
        "production_launch_pack_remaining_gate_stage262",
        "production_hypercare_remaining_gate_stage219",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "phprp-hypercare-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_production_hypercare_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PRODUCTION_HYPERCARE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PRODUCTION_HYPERCARE_MVP.md" in doc
    assert "GOLIVE_ATTESTATION_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PRODUCTION_LAUNCH_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PRODUCTION_HYPERCARE_REMAINING_GATE_MVP.md" in doc
    assert "production_hypercare_live_claimed" in doc
    assert "oncall_rota_live" in doc
