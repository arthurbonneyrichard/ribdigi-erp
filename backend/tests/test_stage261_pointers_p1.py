"""Stage 261 P1 — preflight verification pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "preflight-verification-pack-rg-pointers.json"


def test_preflight_verification_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 261 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["sections_1_3_verified"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "preflight_verification_stage69_v1",
        "commercial_golive_closeout_pack_remaining_gate_stage260",
        "first_commercial_day_pack_remaining_gate_stage259",
        "preflight_verification_remaining_gate_stage201",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pvprp-preflight-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_preflight_verification_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PREFLIGHT_VERIFICATION_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PREFLIGHT_VERIFICATION_MVP.md" in doc
    assert "COMMERCIAL_GOLIVE_CLOSEOUT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "FIRST_COMMERCIAL_DAY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PREFLIGHT_VERIFICATION_REMAINING_GATE_MVP.md" in doc
    assert "sections_1_3_verified" in doc
    assert "preflight_verified_claimed" in doc
