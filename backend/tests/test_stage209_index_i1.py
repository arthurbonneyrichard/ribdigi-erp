"""Stage 209 I1 — pentest remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pentest-remaining-gate.json"


def test_pentest_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 209 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["vendor_pen_test_purchased"] is False
    assert data["live_zap_executed"] is False
    assert data["go_live_claimed"] is False
    assert data["live_soak_executed"] is False
    assert data["distinct_from_stage29_v1_pentest"] is True
    assert data["distinct_from_stage208_pgbouncer_soak_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pe-pentest-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pentest_remaining_gate_doc_i1():
    doc = (ROOT / "docs/PENTEST_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "vendor_pen_test_purchased" in doc
    assert "PENTEST_BLOCKERS_MVP.md" in doc
    assert "PENTEST_PACK_POINTERS_MVP.md" in doc
    assert "Stage 29" in doc
