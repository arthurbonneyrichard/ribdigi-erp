"""Stage 302 P1 — AI provider boundary pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ai-provider-boundary-pack-rg-pointers.json"


def test_ai_provider_boundary_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 302 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["external_llm_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "ai_provider_boundary_stage42",
        "ai_use_disclosure_pack_remaining_gate_stage301",
        "tos_aup_pack_remaining_gate_stage300",
        "ai_use_disclosure_stage42",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "apbprp-llm-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ai_provider_boundary_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/AI_PROVIDER_BOUNDARY_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "AI_PROVIDER_BOUNDARY_MVP.md" in doc
    assert "AI_USE_DISCLOSURE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "TOS_AUP_PACK_REMAINING_GATE_MVP.md" in doc
    assert "AI_USE_DISCLOSURE_MVP.md" in doc
    assert "external_llm_claimed" in doc
    assert "prophet_claimed" in doc
