"""Stage 298 P1 — DPA subprocessor pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "dpa-subprocessor-pack-rg-pointers.json"


def test_dpa_subprocessor_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 298 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["dpa_signed_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "dpa_subprocessor_stage39",
        "commercial_assurance_pack_remaining_gate_stage297",
        "commercial_dpa_pack_remaining_gate_stage292",
        "commercial_dpa_stage77",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "dsprp-dpa-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_dpa_subprocessor_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/DPA_SUBPROCESSOR_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "DPA_SUBPROCESSOR_MVP.md" in doc
    assert "COMMERCIAL_ASSURANCE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_DPA_PACK_REMAINING_GATE_MVP.md" in doc
    assert "COMMERCIAL_DPA_MVP.md" in doc
    assert "dpa_signed_claimed" in doc
    assert "subprocessor_register_live" in doc
