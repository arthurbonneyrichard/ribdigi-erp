"""Stage 328 P1 — loadtest baseline pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "loadtest-baseline-pack-rg-pointers.json"


def test_loadtest_baseline_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 328 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["certified_load_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "loadtest_baseline_remaining_gate_stage225",
        "ops_monitoring_pack_remaining_gate_stage327",
        "hosted_faq_saas_pack_remaining_gate_stage326",
        "load_test_baseline_stage5",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ltbprp-load-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_loadtest_baseline_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LOADTEST_BASELINE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LOADTEST_BASELINE_REMAINING_GATE_MVP.md" in doc
    assert "OPS_MONITORING_PACK_REMAINING_GATE_MVP.md" in doc
    assert "HOSTED_FAQ_SAAS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "LOAD_TEST_BASELINE.md" in doc
    assert "certified_load_claimed" in doc
    assert "live_load_capacity_claimed" in doc
