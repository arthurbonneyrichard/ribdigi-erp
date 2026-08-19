"""Stage 226 I1 — PgBouncer live remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-live-remaining-gate.json"


def test_pgbouncer_live_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 226 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_pgbouncer_claimed"] is False
    assert data["helm_pooler_default_claimed"] is False
    assert data["live_soak_executed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage27_p1_stage29_b2_packaging"] is True
    assert data["distinct_from_stage208_pgbouncer_soak_remaining_gate"] is True
    assert data["distinct_from_stage225_loadtest_baseline_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pbl-live-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_live_remaining_gate_doc_i1():
    doc = (ROOT / "docs/PGBOUNCER_LIVE_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_pgbouncer_claimed" in doc
    assert "PGBOUNCER_LIVE_BLOCKERS_MVP.md" in doc
    assert "PGBOUNCER_LIVE_RG_POINTERS_MVP.md" in doc
    assert "Stage 27" in doc
    assert "Stage 208" in doc
