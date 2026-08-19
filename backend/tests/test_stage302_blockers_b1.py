"""Stage 302 B1 — AI provider boundary pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ai-provider-boundary-pack-rg-blockers.json"


def test_ai_provider_boundary_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 302 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["external_llm_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["external_llm_claimed"] == "REMAINING"
    assert blockers["prophet_claimed"] == "REMAINING"
    assert blockers["paid_model_vendor_required"] == "REMAINING"
    assert blockers["output_pii_scanner_claimed"] == "REMAINING"
    assert blockers["stage42_as_external_llm"] == "NON_CLAIM"
    assert blockers["external_llm_claimed_flag"] == "false"
    assert blockers["prophet_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "apbprb-llm-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ai_provider_boundary_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/AI_PROVIDER_BOUNDARY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "external_llm_claimed" in doc
    assert "prophet_claimed" in doc
    assert "Stage 42" in doc
