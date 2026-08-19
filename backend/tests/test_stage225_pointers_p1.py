"""Stage 225 P1 — loadtest baseline RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "loadtest-baseline-rg-pointers.json"


def test_loadtest_baseline_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 225 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["certified_load_claimed"] is False
    assert data["live_load_capacity_claimed"] is False
    for topic in (
        "loadtest_baseline_stage5_l1_stage18_t1",
        "load_capacity_remaining_gate_stage224",
        "load_cert_pack_remaining_gate_stage223",
        "load_capacity_stage26_c1",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ltbp-certified-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_loadtest_baseline_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LOADTEST_BASELINE_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LOAD_TEST_BASELINE.md" in doc
    assert "LOAD_CAPACITY_REMAINING_GATE_MVP.md" in doc
    assert "LOAD_CERT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "certified_load_claimed" in doc
