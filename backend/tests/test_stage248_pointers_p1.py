"""Stage 248 P1 — release pipeline pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "release-pipeline-pack-rg-pointers.json"


def test_release_pipeline_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 248 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["mvp_release_candidate_signed"] is False
    assert data["release_pipeline_live_claimed"] is False
    for topic in (
        "release_pipeline_stage65_r1",
        "implementation_onboarding_pack_remaining_gate_stage247",
        "business_pilot_pack_remaining_gate_stage246",
        "staging_gha_pack_remaining_gate_stage229",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "rpprp-rc-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_release_pipeline_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/RELEASE_PIPELINE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "RELEASE_PIPELINE_MVP.md" in doc
    assert "IMPLEMENTATION_ONBOARDING_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BUSINESS_PILOT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "STAGING_GHA_PACK_REMAINING_GATE_MVP.md" in doc
    assert "mvp_release_candidate_signed" in doc
    assert "release_pipeline_live_claimed" in doc
